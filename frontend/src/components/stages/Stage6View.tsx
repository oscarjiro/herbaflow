/**
 * Stage6View — Stage 6 STRING protein–protein interaction (PPI) network over the
 * Stage-5 overlap targets.
 *
 * Unlike Stage 5, Stage 6 IS param-bearing (the `ppi` group: min_confidence,
 * max_proteins, allow_top_n_cap, network_type) and has a special **blocked**
 * ("overlap too large") state.
 *
 * Two states of `stage_results["6"]`:
 *  - blocked  → `{ blocked:true, reason:"overlap_too_large", overlap_count, max_proteins }`
 *    Render an "overlap too large" prompt instead of the network table, with an
 *    "Enable top-N & Redo" affordance (Redo that flips `allow_top_n_cap: true`) and
 *    a hint to narrow the inputs upstream. Still render the param panel + ApprovalBar
 *    (guided parks here).
 *  - computed → summary cards (node/edge counts, min_confidence, network_type, unmapped),
 *    an edge-list table (source, target, confidence) + CSV of the edges.
 *
 * Always: the ppi param panel (Redo via reset-from/6 with only the changed `ppi`
 * values — incl. the two enum selects) and the StageDataSources footer.
 *
 * The stage header, ApprovalBar, and StaleNotice are owned by the StageView shell.
 */

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead } from "../../api/types.gen";
import { resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import {
  PPI_BOOLEAN_PARAMS,
  PPI_NUMERIC_PARAMS,
  PPI_PARAMS,
  PPI_SELECT_PARAMS,
} from "../../contract";
import { humanizeValue } from "../../contract/labels";
import { uniprotUrl } from "../../lib/externalUrls";
import { formatCount } from "../../lib/format";
import { exportArtifactUrl } from "../../lib/exportUrl";
import type cytoscape from "cytoscape";
import { useChartColors } from "@/lib/chartTheme";
import { NetworkGraph } from "@/components/charts/NetworkGraph";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StageSummaryCard } from "./StageSummaryCard";

// ---------------------------------------------------------------------------
// Local types for the Stage 6 result shapes (narrowed from unknown)
// ---------------------------------------------------------------------------

type Stage6Node = {
  gene_symbol: string;
  string_id: string | null;
  target_id?: string | null;
  uniprot_accession?: string | null;
};
type Stage6Edge = { source: string; target: string; confidence: number };

type Stage6Computed = {
  state: "computed";
  nodes: Stage6Node[];
  edges: Stage6Edge[];
  node_count: number;
  edge_count: number;
  min_confidence: number;
  network_type: string;
  unmapped: string[];
  capped: { applied: boolean; max_proteins: number; ranked_by: string };
  count: number;
  flags?: string[];
};

type Stage6Blocked = {
  blocked: true;
  reason: string;
  overlap_count: number;
  max_proteins: number;
};

type Stage6Result = Stage6Computed | Stage6Blocked;

type Stage7Hub = {
  rank?: number;
  target_id?: string | null;
  gene_symbol: string;
  mcc: number;
};

type PpiParams = Record<string, number | boolean | string>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function isBlocked(r: Stage6Result): r is Stage6Blocked {
  return (r as Stage6Blocked).blocked === true;
}

export const S6_CSV_HEADER = "source,target,confidence";

export function buildS6CsvRows(edges: Stage6Edge[]): unknown[][] {
  return edges.map((e) => [e.source, e.target, e.confidence]);
}

type NetworkElements = {
  elements: cytoscape.ElementDefinition[];
  isolated: string[];
  maxDegree: number;
};

/**
 * Build the flat Cytoscape elements array for the PPI network.
 *
 * Edges connect by a resolver that maps BOTH gene_symbol and string_id to the
 * canonical node id (the gene symbol), so an edge endpoint expressed either way
 * still links. Only edges whose both endpoints resolve to a known node are kept;
 * only nodes that appear in at least one kept edge are added (isolated nodes are
 * collected for the not-connected tray, not drawn). MCC (from Stage 7) sizes the
 * hub nodes; hub nodes are those present in the MCC map.
 */
export function buildNetworkElements(
  nodes: Stage6Node[],
  edges: Stage6Edge[],
  hubs: Stage7Hub[],
): NetworkElements {
  // Map every node key (gene_symbol and string_id) to the canonical id.
  const idByKey = new Map<string, string>();
  for (const n of nodes) {
    const id = n.gene_symbol;
    idByKey.set(n.gene_symbol, id);
    if (n.string_id) idByKey.set(n.string_id, id);
  }
  const resolve = (endpoint: string) => idByKey.get(endpoint);

  // MCC by gene_symbol and by target_id; hubs are the keys of this map.
  const mccByKey = new Map<string, number>();
  for (const h of hubs) {
    mccByKey.set(h.gene_symbol, h.mcc);
    if (h.target_id) mccByKey.set(h.target_id, h.mcc);
  }

  const elements: cytoscape.ElementDefinition[] = [];
  const connected = new Set<string>();
  const degreeById = new Map<string, number>();

  edges.forEach((e, i) => {
    const source = resolve(e.source);
    const target = resolve(e.target);
    if (!source || !target) return;
    elements.push({ data: { id: `e-${i}`, source, target, weight: e.confidence } });
    connected.add(source);
    connected.add(target);
    degreeById.set(source, (degreeById.get(source) ?? 0) + 1);
    degreeById.set(target, (degreeById.get(target) ?? 0) + 1);
  });

  let maxDegree = 0;
  const isolated: string[] = [];
  for (const n of nodes) {
    const id = n.gene_symbol;
    if (!connected.has(id)) {
      isolated.push(id);
      continue;
    }
    const mcc =
      mccByKey.get(n.gene_symbol) ?? (n.target_id ? mccByKey.get(n.target_id) : undefined) ?? 0;
    const degree = degreeById.get(id) ?? 0;
    if (degree > maxDegree) maxDegree = degree;
    elements.push({
      data: {
        id,
        label: n.gene_symbol,
        mcc,
        degree,
        hub: mccByKey.has(n.gene_symbol) ? "true" : "false",
      },
    });
  }

  return { elements, isolated, maxDegree };
}

/** Build the Cytoscape stylesheet from resolved hf-* color strings. */
function buildNetworkStylesheet(
  colors: ReturnType<typeof useChartColors>,
  minConfidence: number,
  maxDegree: number,
): cytoscape.StylesheetJson {
  // Uniform node size — connectivity is conveyed by the degree colour ramp, not by
  // node area (per-node MCC sizing read as noisy and uneven on a flat backdrop).
  const sizeStyle = { width: 28, height: 28 };

  // Degree-ramp color: faint (low connectivity) → deep (high connectivity).
  // When maxDegree === 0 (no edges) fall back to a flat mid-tone to avoid a
  // mapData divide-by-zero.
  const bgColor =
    maxDegree > 0
      ? `mapData(degree, 0, ${maxDegree}, ${colors.sageFaint}, ${colors.sageDeep})`
      : colors.sageSoft;

  return [
    {
      selector: "node",
      style: {
        ...sizeStyle,
        "background-color": bgColor,
        label: "data(label)",
        color: colors.fg1,
        "font-size": 9,
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 2,
      },
    },
    {
      selector: "edge",
      style: {
        width: `mapData(weight, ${minConfidence}, 1, 1, 4)`,
        "line-color": colors.border,
        "curve-style": "bezier",
        opacity: 0.6,
      },
    },
  ] as cytoscape.StylesheetJson;
}

// ---------------------------------------------------------------------------
// Stage6View
// ---------------------------------------------------------------------------

export function Stage6View({ data }: { data: AnalysisRead }) {
  const stage6 = data.stage_results?.["6"] as Stage6Result | undefined;
  const ppiParams = (data.parameters as Record<string, unknown> | undefined)?.ppi as
    | PpiParams
    | undefined;

  const qc = useQueryClient();
  const redo = useMutation({
    mutationFn: (changed: PpiParams) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 6 },
        body: { parameters: { "6": changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo("Re-running from step 6");
    },
    onError: (error) => notifyError(error as Problem),
  });

  const computed = stage6 && !isBlocked(stage6) ? stage6 : undefined;
  const edges = useMemo(() => computed?.edges ?? [], [computed]);
  const csvRows = useMemo(() => buildS6CsvRows(edges), [edges]);

  const colors = useChartColors();
  const hubs = useMemo(
    () => (data.stage_results?.["7"] as { hubs?: Stage7Hub[] } | undefined)?.hubs ?? [],
    [data.stage_results],
  );
  const network = useMemo(
    () => buildNetworkElements(computed?.nodes ?? [], computed?.edges ?? [], hubs),
    [computed, hubs],
  );
  const accessionByNodeKey = useMemo(() => {
    const map = new Map<string, string>();
    for (const node of computed?.nodes ?? []) {
      if (!node.uniprot_accession) continue;
      map.set(node.gene_symbol, node.uniprot_accession);
      if (node.string_id) map.set(node.string_id, node.uniprot_accession);
    }
    return map;
  }, [computed]);
  const stylesheet = useMemo(
    () => buildNetworkStylesheet(colors, computed?.min_confidence ?? 0, network.maxDegree),
    [colors, computed, network.maxDegree],
  );

  if (!stage6) return null;

  const blocked = isBlocked(stage6) ? stage6 : undefined;

  function renderGeneLink(gene: string) {
    const accession = accessionByNodeKey.get(gene);
    if (!accession) return <span>{gene}</span>;
    return <ExternalLink href={uniprotUrl(accession)}>{gene}</ExternalLink>;
  }

  // Column definitions — edge endpoints display gene symbols and link through the matching
  // Stage-6 node accession. Links are display-only and excluded from the CSV.
  const columns: ColumnDef<Stage6Edge>[] = [
    {
      id: "source",
      header: "Source",
      enableSorting: true,
      cell: ({ row }) => renderGeneLink(row.original.source),
    },
    {
      id: "target",
      header: "Target",
      enableSorting: true,
      cell: ({ row }) => renderGeneLink(row.original.target),
    },
    {
      id: "confidence",
      header: "Confidence",
      enableSorting: true,
      meta: { className: "num" },
      cell: ({ row }) => row.original.confidence,
    },
  ];

  const paramPanel = ppiParams ? (
    <ParamPanel
      params={ppiParams}
      meta={PPI_PARAMS}
      numericKeys={PPI_NUMERIC_PARAMS}
      booleanKeys={PPI_BOOLEAN_PARAMS}
      selectKeys={PPI_SELECT_PARAMS}
      title="PPI network parameters"
      disabled={redo.isPending}
      onRedo={(changed) => redo.mutate(changed)}
    />
  ) : null;

  return (
    <section className="flex flex-col gap-6">
      <StageDataSources stage={6} />

      {blocked ? (
        // ----- Overlap-too-large prompt -----
        <Card role="status">
          <CardContent className="flex flex-col gap-4 pt-6">
            <div className="flex items-center gap-2">
              <Badge variant="destructive">Overlap too large</Badge>
            </div>
            <p className="text-sm">
              The overlap of {blocked.overlap_count} proteins exceeds the STRING ceiling of{" "}
              {blocked.max_proteins}. Building a network this large is unreliable, so it was not
              queried.
            </p>
            <p className="text-muted-foreground text-sm">
              Either enable the top-N cap to proceed on the {blocked.max_proteins} highest-ranked
              proteins, or narrow the inputs upstream (raise the Stage 3 / Stage 4 thresholds, or
              tighten the overlap) and re-run.
            </p>
            <div>
              <Button
                type="button"
                disabled={redo.isPending}
                onClick={() => redo.mutate({ allow_top_n_cap: true })}
                aria-label="Enable top-N cap and Redo"
              >
                Enable top-N &amp; Redo
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        computed && (
          <>
            {/* Summary cards */}
            <div className="flex flex-wrap gap-3">
              <StageSummaryCard
                value={formatCount(computed.node_count)}
                label="nodes"
                ariaLabel={`${computed.node_count} nodes`}
              />
              <StageSummaryCard
                value={formatCount(computed.edge_count)}
                label="edges"
                ariaLabel={`${computed.edge_count} edges`}
              />
              <StageSummaryCard
                value={computed.min_confidence}
                label="min confidence"
                ariaLabel={`min confidence ${computed.min_confidence}`}
                muted
              />
              <StageSummaryCard
                value={humanizeValue(computed.network_type)}
                label="network type"
                ariaLabel={`network type ${humanizeValue(computed.network_type)}`}
                muted
              />
              <StageSummaryCard
                value={formatCount(computed.unmapped.length)}
                label="unmapped"
                ariaLabel={`${computed.unmapped.length} unmapped`}
                muted
              />
            </div>

            {computed.capped.applied && (
              <p className="text-muted-foreground text-sm" role="status">
                Capped to the top {computed.capped.max_proteins} proteins by{" "}
                {computed.capped.ranked_by}.
              </p>
            )}

            {computed.edge_count === 0 && (
              <p className="text-muted-foreground text-sm" role="status">
                No interactions among the overlap targets at this confidence floor.
              </p>
            )}

            {/* Interactive PPI network (shown once this step has drawable elements; the deterministic
                server PNG stays in the export bundle). Blocked / empty states have their own
                UI above, so the graph simply does not render then. */}
            {network.elements.length > 0 && (
              <>
                <NetworkGraph
                  title="Protein-protein interaction network"
                  filename="ppi_network.png"
                  elements={network.elements}
                  stylesheet={stylesheet}
                  actions={
                    <Button variant="secondary" size="sm" asChild>
                      <a
                        href={exportArtifactUrl(data.analysis_id, "stage6_ppi_network.png")}
                        download="stage6_ppi_network.png"
                        aria-label="Download STRING image"
                      >
                        <svg
                          aria-hidden="true"
                          xmlns="http://www.w3.org/2000/svg"
                          width="14"
                          height="14"
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="1.5"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                          <polyline points="7 10 12 15 17 10" />
                          <line x1="12" y1="15" x2="12" y2="3" />
                        </svg>
                        Download STRING image
                      </a>
                    </Button>
                  }
                  nodeTooltip={(d) =>
                    `Protein: ${String(d.label ?? "")} · Degree: ${d.degree ?? 0}`
                  }
                  tray={
                    network.isolated.length > 0 ? (
                      <p className="text-muted-foreground mt-3 text-sm">
                        Not connected at this confidence: {network.isolated.join(", ")}
                      </p>
                    ) : undefined
                  }
                />
              </>
            )}

            {/* Edge-list table card */}
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-3">
                  <CsvDownloadButton
                    header={S6_CSV_HEADER}
                    rows={csvRows}
                    filename="ppi.csv"
                    label="Download CSV"
                  />
                </div>
              </CardHeader>
              <CardContent className="px-0">
                <DataTable columns={columns} data={edges} />
              </CardContent>
            </Card>
          </>
        )
      )}

      {/* PPI param panel — always shown (raise the cap / change settings + Redo) */}
      {paramPanel}
    </section>
  );
}
