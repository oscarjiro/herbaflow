/**
 * Stage5View — overlap of Stage 3 (compound→target) ∩ Stage 4 (disease→target).
 *
 * Stage 5 has NO parameters and is NOT an entity stage. It is a read-only view:
 *  - Summary cards: overlap count + compound-side / disease-side set sizes
 *  - Overlap DataTable (columns in spec order):
 *      1. UniProt accession → ExternalLink (uniprotUrl)
 *      2. Gene symbol
 *      3. Compound source(s) → ExpandableListCell of compound-name chips
 *         HIDDEN when the plant side is manual_targets (stage_state["3"] === "user_provided";
 *         in that mode Stage 3 has no compound edges so there are no source compounds).
 *    No delete column, no add box, no param panel.
 *  - DataTable owns sorting and pagination
 *  - CSV download (header: gene_symbol,uniprot_accession,opentargets_score,source_url — unchanged)
 *  - StageDataSources footer
 *
 * protein_name: absent from the Stage-5 overlap row shape — not rendered, not invented.
 *
 * Compound source(s) derivation: the overlap row itself carries no compound-source list.
 * We derive it from Stage 3's compound_targets edges (grouped by target_id → compound canonical names
 * from stage_results["2"].passed). For manual-target runs (stage_state["3"] === "user_provided")
 * no edges exist and the column is hidden entirely.
 *
 * The stage header and ApprovalBar are owned by the StageView shell.
 * No param panel, no Redo, no entity add/remove, no TargetValidateBox.
 */

import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead } from "../../api/types.gen";
import { uniprotUrl } from "../../lib/externalUrls";
import { formatCount } from "../../lib/format";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { ChartFrame } from "@/components/charts/ChartFrame";
import { OverlapVenn } from "@/components/charts/OverlapVenn";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { ExpandableListCell } from "@/components/ui/ExpandableListCell";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { StageDataSources } from "./StageDataSources";
import { StageSummaryCard } from "./StageSummaryCard";

// ---------------------------------------------------------------------------
// Local types for the Stage 5 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type OverlapRow = {
  target_id: string;
  gene_symbol: string | null;
  uniprot_accession: string | null;
  opentargets_score: number | null;
};

type Stage5Result = {
  overlap: OverlapRow[];
  count: number;
  compound_target_count: number;
  disease_target_count: number;
  unmapped_count: number;
  state: string;
  flags?: string[];
};

// Stage 3 compound_targets edge — needed to derive per-target source-compound names.
type CompoundTargetEdge = {
  compound_id: string;
  target_id: string;
};

type Stage3Result = {
  compound_targets?: CompoundTargetEdge[];
};

// Stage 2 passed compound row — carries the canonical_name for display.
type Stage2Passed = {
  compound_id: string;
  canonical_name: string | null;
};

// Derived view row — extends OverlapRow with the compound-source list.
type OverlapViewRow = OverlapRow & {
  source_compounds: string[];
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * CSV header — kept exactly as the original (raw values, no display rounding).
 * source_url is derived from the UniProt accession when present.
 */
const S5_CSV_HEADER = "gene_symbol,uniprot_accession,opentargets_score,source_url";

function buildS5CsvRows(rows: OverlapRow[]): unknown[][] {
  return rows.map((r) => {
    const acc = r.uniprot_accession;
    const sourceUrl = acc ? uniprotUrl(acc) : null;
    return [r.gene_symbol, acc, r.opentargets_score, sourceUrl];
  });
}

/**
 * Enrich each overlap row with the per-target compound-source list derived from Stage 3's
 * compound_targets edges and Stage 2's passed compound names. Returns the same rows if no
 * Stage 3 edge data is available (manual-target runs have no edges).
 */
function buildOverlapViewRows(
  overlap: OverlapRow[],
  stage3: Stage3Result | undefined,
  nameById: Map<string, string | null>,
): OverlapViewRow[] {
  const edgesByTarget = new Map<string, string[]>();
  for (const edge of stage3?.compound_targets ?? []) {
    const list = edgesByTarget.get(edge.target_id) ?? [];
    list.push(edge.compound_id);
    edgesByTarget.set(edge.target_id, list);
  }

  return overlap.map((row) => {
    const compoundIds = Array.from(new Set(edgesByTarget.get(row.target_id) ?? []));
    const source_compounds = compoundIds.map((cid) => nameById.get(cid) ?? cid).filter(Boolean);
    return { ...row, source_compounds };
  });
}

// ---------------------------------------------------------------------------
// Stage5View
// ---------------------------------------------------------------------------

export function Stage5View({ data }: { data: AnalysisRead }) {
  const stage5 = data.stage_results?.["5"] as Stage5Result | undefined;
  const stage3 = data.stage_results?.["3"] as Stage3Result | undefined;
  const stage2 = data.stage_results?.["2"] as { passed?: Stage2Passed[] } | undefined;

  // stage_state["3"] === "user_provided" ↔ manual_targets plant input mode; no compound edges exist.
  const stageState3 = (data as { stage_state?: Record<string, string> }).stage_state?.["3"];
  const isManualTargets = stageState3 === "user_provided";

  // Build compound-name map from Stage 2 passed list.
  const nameById = useMemo<Map<string, string | null>>(
    () => new Map((stage2?.passed ?? []).map((c) => [c.compound_id, c.canonical_name])),
    [stage2],
  );

  // Enrich overlap rows with source_compounds derived from Stage 3 edges.
  const overlapViewRows = useMemo(
    () => buildOverlapViewRows(stage5?.overlap ?? [], stage3, nameById),
    [stage5, stage3, nameById],
  );

  const csvRows = useMemo(() => buildS5CsvRows(stage5?.overlap ?? []), [stage5]);

  if (!stage5) return null;

  // Column definitions — spec-aligned, in the required order. Read-only: no delete/actions column.
  const columns: ColumnDef<OverlapViewRow>[] = [
    // 1. UniProt accession → ExternalLink to UniProt entry page.
    {
      id: "uniprot",
      header: "UniProt",
      cell: ({ row }) => {
        const acc = row.original.uniprot_accession;
        if (!acc) return <span className="text-hf-fg-3">—</span>;
        return <ExternalLink href={uniprotUrl(acc)}>{acc}</ExternalLink>;
      },
    },
    // 2. Gene symbol.
    {
      id: "gene_symbol",
      header: "Gene symbol",
      cell: ({ row }) => row.original.gene_symbol ?? <span className="text-hf-fg-3">—</span>,
    },
    // 3. Compound source(s) — HIDDEN for manual-target runs (no compound edges exist).
    //    Rendered as ExpandableListCell of compound-name chips for app-enriched runs.
    ...(isManualTargets
      ? []
      : ([
          {
            id: "compound_sources",
            header: "Compound source(s)",
            enableSorting: false,
            cell: ({ row }: { row: { original: OverlapViewRow } }) => (
              <ExpandableListCell items={row.original.source_compounds} />
            ),
          },
        ] as ColumnDef<OverlapViewRow>[])),
  ];

  return (
    <section className="flex flex-col gap-6">
      <StageDataSources stage={5} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <StageSummaryCard
          value={formatCount(stage5.count)}
          label="overlap targets"
          ariaLabel={`${stage5.count} overlap targets`}
        />
        <StageSummaryCard
          value={formatCount(stage5.compound_target_count)}
          label="compound-side targets"
          ariaLabel={`${stage5.compound_target_count} compound-side targets`}
          muted
        />
        <StageSummaryCard
          value={formatCount(stage5.disease_target_count)}
          label="disease-side targets"
          ariaLabel={`${stage5.disease_target_count} disease-side targets`}
          muted
        />
      </div>

      {/* Interactive Venn diagram (shown once this step has results; hidden when both counts are zero) */}
      {(stage5.compound_target_count > 0 || stage5.disease_target_count > 0) && (
        <ChartFrame title="Target overlap" filename="target_overlap.png">
          <OverlapVenn
            compoundCount={stage5.compound_target_count}
            diseaseCount={stage5.disease_target_count}
            overlapCount={stage5.count}
            overlapGenes={stage5.overlap
              .map((r) => r.gene_symbol)
              .filter((g): g is string => Boolean(g))}
          />
        </ChartFrame>
      )}

      {stage5.count === 0 && (
        <p className="text-sm text-[color:var(--hf-fg-3)]" role="status">
          No targets overlap between compound–target and disease–target sets.
        </p>
      )}

      {/* Overlap table card */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <CsvDownloadButton
              header={S5_CSV_HEADER}
              rows={csvRows}
              filename="overlap.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="px-0">
          <div className="table-wrapper">
            <DataTable
              columns={columns}
              data={overlapViewRows}
              emptyMessage="No shared targets found."
            />
          </div>
        </CardContent>
      </Card>
    </section>
  );
}
