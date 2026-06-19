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
 *    a paginated edge-list table (source, target, confidence) + CSV of the edges.
 *
 * Always: the ppi param panel (Redo via reset-from/6 with only the changed `ppi`
 * values — incl. the two enum selects), the StageDataSources footer, the ApprovalBar
 * (mirroring Stage5View), and the StaleNotice if stale.
 */

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis, resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import {
  PPI_BOOLEAN_PARAMS,
  PPI_NUMERIC_PARAMS,
  PPI_PARAMS,
  PPI_SELECT_PARAMS,
} from "../../contract";
import type cytoscape from "cytoscape";
import { useStaleState } from "../../hooks/useStaleState";
import { useChartColors } from "@/lib/chartTheme";
import { NetworkGraph } from "@/components/charts/NetworkGraph";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { Eyebrow } from "@/components/ui/editorial";
import { ApprovalBar } from "./ApprovalBar";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";

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

const PAGE_SIZES = [10, 20, 50] as const;

function isBlocked(r: Stage6Result): r is Stage6Blocked {
  return (r as Stage6Blocked).blocked === true;
}

const S6_CSV_HEADER = "source,target,confidence";

function buildS6CsvRows(edges: Stage6Edge[]): unknown[][] {
  return edges.map((e) => [e.source, e.target, e.confidence]);
}

type NetworkElements = {
  elements: cytoscape.ElementDefinition[];
  isolated: string[];
  maxMcc: number;
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
function buildNetworkElements(
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

  edges.forEach((e, i) => {
    const source = resolve(e.source);
    const target = resolve(e.target);
    if (!source || !target) return;
    elements.push({ data: { id: `e-${i}`, source, target, weight: e.confidence } });
    connected.add(source);
    connected.add(target);
  });

  let maxMcc = 0;
  const isolated: string[] = [];
  for (const n of nodes) {
    const id = n.gene_symbol;
    if (!connected.has(id)) {
      isolated.push(id);
      continue;
    }
    const mcc =
      mccByKey.get(n.gene_symbol) ?? (n.target_id ? mccByKey.get(n.target_id) : undefined) ?? 0;
    if (mcc > maxMcc) maxMcc = mcc;
    elements.push({
      data: { id, label: n.gene_symbol, mcc, hub: mccByKey.has(n.gene_symbol) ? "true" : "false" },
    });
  }

  return { elements, isolated, maxMcc };
}

/** Build the Cytoscape stylesheet from resolved hf-* color strings. */
function buildNetworkStylesheet(
  colors: ReturnType<typeof useChartColors>,
  minConfidence: number,
  maxMcc: number,
): cytoscape.StylesheetJson {
  const sizeStyle =
    maxMcc > 0
      ? {
          width: `mapData(mcc, 0, ${maxMcc}, 16, 52)`,
          height: `mapData(mcc, 0, ${maxMcc}, 16, 52)`,
        }
      : { width: 24, height: 24 };
  return [
    {
      selector: "node",
      style: {
        ...sizeStyle,
        "background-color": colors.sage,
        label: "data(label)",
        color: colors.fg1,
        "font-size": 9,
        "text-valign": "bottom",
        "text-halign": "center",
        "text-margin-y": 2,
      },
    },
    {
      selector: 'node[hub = "true"]',
      style: { "background-color": colors.sageDeep },
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
  const { anyStale } = useStaleState(data);

  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (error) => notifyError(error as Problem),
  });
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

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

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
  const stylesheet = useMemo(
    () => buildNetworkStylesheet(colors, computed?.min_confidence ?? 0, network.maxMcc),
    [colors, computed, network.maxMcc],
  );

  if (!stage6) return null;

  const blocked = isBlocked(stage6) ? stage6 : undefined;

  // Pagination over edges (computed only)
  const effectivePageSize = pageSize === "all" ? Math.max(1, edges.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(edges.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visibleEdges = edges.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  const isComplete = data.status === "complete";

  // Column definitions — SAME columns + order as the prior <table>
  const columns: ColumnDef<Stage6Edge>[] = [
    {
      id: "source",
      header: "Source",
      cell: ({ row }) => row.original.source,
    },
    {
      id: "target",
      header: "Target",
      cell: ({ row }) => row.original.target,
    },
    {
      id: "confidence",
      header: "Confidence",
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
      {/* Editorial header */}
      <div className="flex flex-col gap-1">
        <Eyebrow>Step 6</Eyebrow>
        <h2 className="hf-heading-serif">Step 6: PPI Network</h2>
      </div>

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
              <div
                className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
                aria-label={`${computed.node_count} nodes`}
              >
                <span className="hf-num text-2xl font-semibold tabular-nums">
                  {computed.node_count}
                </span>
                <span className="text-muted-foreground text-xs">nodes</span>
              </div>
              <div
                className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
                aria-label={`${computed.edge_count} edges`}
              >
                <span className="hf-num text-2xl font-semibold tabular-nums">
                  {computed.edge_count}
                </span>
                <span className="text-muted-foreground text-xs">edges</span>
              </div>
              <div
                className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
                aria-label={`min confidence ${computed.min_confidence}`}
              >
                <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
                  {computed.min_confidence}
                </span>
                <span className="text-muted-foreground text-xs">min confidence</span>
              </div>
              <div
                className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
                aria-label={`network type ${computed.network_type}`}
              >
                <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
                  {computed.network_type}
                </span>
                <span className="text-muted-foreground text-xs">network type</span>
              </div>
              <div
                className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
                aria-label={`${computed.unmapped.length} unmapped`}
              >
                <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
                  {computed.unmapped.length}
                </span>
                <span className="text-muted-foreground text-xs">unmapped</span>
              </div>
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

            {/* Edge-list table card */}
            <Card>
              <CardHeader>
                <div className="flex flex-wrap items-center gap-3">
                  <div className="flex items-center gap-2">
                    <label htmlFor="t6-page-size" className="text-muted-foreground text-sm">
                      Rows per page
                    </label>
                    <select
                      id="t6-page-size"
                      className="bg-background rounded border px-2 py-1 text-sm"
                      value={pageSize}
                      onChange={(e) => {
                        const v = e.target.value;
                        setPageSize(v === "all" ? "all" : Number(v));
                        setPage(0);
                      }}
                    >
                      {PAGE_SIZES.map((s) => (
                        <option key={s} value={s}>
                          {s}
                        </option>
                      ))}
                      <option value="all">All</option>
                    </select>
                  </div>
                  <CsvDownloadButton
                    header={S6_CSV_HEADER}
                    rows={csvRows}
                    filename="ppi-edges.csv"
                    label="Download CSV"
                  />
                </div>
              </CardHeader>
              <CardContent className="px-0">
                <DataTable columns={columns} data={visibleEdges} />
              </CardContent>

              {/* Pagination */}
              {pageSize !== "all" && totalPages > 1 && (
                <div className="flex items-center justify-center gap-3 px-6 pb-4">
                  <button
                    className="hf-btn text-sm"
                    disabled={currentPage === 0}
                    onClick={() => setPage((p) => p - 1)}
                  >
                    Previous
                  </button>
                  <span className="text-muted-foreground text-sm">
                    Page {currentPage + 1} / {totalPages}
                  </span>
                  <button
                    className="hf-btn text-sm"
                    disabled={currentPage >= totalPages - 1}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    Next
                  </button>
                </div>
              )}
            </Card>
          </>
        )
      )}

      {/* Interactive PPI network (complete-only; the deterministic server PNG
          stays in the export bundle). Blocked / empty states have their own UI
          above, so the graph simply does not render then. */}
      {isComplete && computed && computed.nodes.length > 0 && (
        <NetworkGraph
          title="Interaction network"
          filename="ppi_network.png"
          elements={network.elements}
          stylesheet={stylesheet}
          tray={
            network.isolated.length > 0 ? (
              <p className="text-muted-foreground mt-3 text-sm">
                Not connected at this confidence: {network.isolated.join(", ")}
              </p>
            ) : undefined
          }
        />
      )}

      {/* PPI param panel — always shown (raise the cap / change settings + Redo) */}
      {paramPanel}

      <ApprovalBar
        stage={6}
        status={data.status}
        currentStage={data.current_stage}
        disabled={Boolean(blocked) || (computed?.node_count ?? 0) === 0 || anyStale}
        disabledReason={
          anyStale
            ? "Run the updated step before continuing."
            : blocked
              ? "Overlap too large. Enable the top-N cap and Redo, or narrow the inputs."
              : "No PPI nodes. Adjust the parameters and Redo, or narrow the inputs."
        }
        pending={advance.isPending}
        onApprove={() => advance.mutate()}
      />
    </section>
  );
}
