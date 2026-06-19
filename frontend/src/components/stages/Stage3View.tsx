/**
 * Stage3View — compound → target identification results.
 *
 * Renders:
 *  - Editorial header (Eyebrow + serif h2) with summary count cards: target count,
 *    coverage %, and per-source edge counts (ChEMBL bioactivity / PubChem BioAssay)
 *  - Targets DataTable (one row per target): gene symbol, UniProt accession (linked),
 *    evidence/method(s), # compounds, an edit tag badge, and an in-table delete action
 *  - Pagination (10 / 20 / 50 / all) and a CsvDownloadButton keyed on gene symbol +
 *    UniProt accession + method + source_compounds + source_url (NEVER a UUID column)
 *  - Per-compound coverage DataTable (0-coverage rows always visible)
 *  - Target remove via the in-table delete column; add via a standalone EntityAddControl +
 *    TargetValidateBox (editStage). User-removed rows are hidden from the table and the CSV.
 *  - ParamPanel + Redo (resetFrom) and ApprovalBar
 *  - StpDialog for manual SwissTargetPrediction paste-back
 *
 * State handling (stage_state["3"]):
 *  - "not_applicable" → greyed/disabled note
 *  - "user_provided"  → targets list only (no compounds, no coverage, no STP)
 *  - otherwise (computed) → full view
 */

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead, ResolvedTarget } from "../../api/types.gen";
import { advanceAnalysis, editStage, resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import { MAX_TARGETS, TARGET_NUMERIC_PARAMS, TARGET_PARAMS } from "../../contract";
import { atMinEntities, isUserRemoved } from "../../lib/entities";
import { formatSig } from "../../lib/format";
import { useAddWithDedup } from "../../hooks/useAddWithDedup";
import { useStaleState } from "../../hooks/useStaleState";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataTable } from "@/components/ui/DataTable";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { Eyebrow } from "@/components/ui/editorial";
import { AlreadyInRunNote } from "./AlreadyInRunNote";
import { ApprovalBar } from "./ApprovalBar";
import { EntityAddControl } from "./EntityAddControl";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StageEntityContext } from "./StageEntityContext";
import { StaleNotice } from "./StaleNotice";
import { StpDialog, type StpCompound } from "./StpDialog";
import { TargetValidateBox } from "../TargetValidateBox";

// ---------------------------------------------------------------------------
// Local types for the Stage 3 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type TargetTag = "computed" | "user-added" | "user-removed" | string;

type TargetEntry = {
  target_id: string;
  canonical_name: string | null;
  tag: TargetTag;
  // Carried on the row by the manual/edit prefill (user_provided mode has no edges); a computed
  // row leaves these undefined and the accession comes from the compound_targets edges instead.
  uniprot_accession?: string | null;
  source_url?: string | null;
};

type CompoundTargetEdge = {
  compound_id: string;
  target_id: string;
  prediction_method: "chembl_bioactivity" | "pubchem_bioassay" | "stp_import" | string;
  pchembl_value: number | null;
  score: number | null;
  source_url: string | null;
  uniprot_accession: string | null;
};

type Stage3Result = {
  targets: TargetEntry[];
  compound_targets: CompoundTargetEdge[];
  per_compound: Record<string, { coverage: number }>;
  coverage_pct: number;
  count: number;
  state: string;
};

type Stage2Passed = {
  compound_id: string;
  canonical_name: string | null;
  smiles?: string | null;
};

// A derived, per-target view row.
type TargetRow = {
  target_id: string;
  gene_symbol: string;
  uniprot_accession: string | null;
  source_url: string | null;
  methods: string[];
  compound_count: number;
  source_compounds: string[];
  tag: TargetTag;
};

// A derived, per-compound coverage view row.
type CoverageRow = {
  compound_id: string;
  compound: string;
  coverage: number;
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 20, 50] as const;

const METHOD_LABELS: Record<string, string> = {
  chembl_bioactivity: "ChEMBL",
  pubchem_bioassay: "PubChem BioAssay",
};

function methodLabel(m: string): string {
  return METHOD_LABELS[m] ?? m;
}

/**
 * Group edges by target_id, join with the tagged targets list. User-removed targets are filtered
 * out of the view (and so out of the CSV); their data still persists for re-run / both-sides
 * exclusion. `nameById` maps a compound_id → its display name for the source-compounds column.
 */
function buildTargetRows(stage3: Stage3Result, nameById: Map<string, string | null>): TargetRow[] {
  const edgesByTarget = new Map<string, CompoundTargetEdge[]>();
  for (const edge of stage3.compound_targets) {
    const list = edgesByTarget.get(edge.target_id) ?? [];
    list.push(edge);
    edgesByTarget.set(edge.target_id, list);
  }

  return stage3.targets
    .filter((t) => !isUserRemoved(t.tag)) // hidden; data still persists
    .map((t) => {
      const edges = edgesByTarget.get(t.target_id) ?? [];
      const methods = Array.from(new Set(edges.map((e) => e.prediction_method)));
      const compoundIds = Array.from(new Set(edges.map((e) => e.compound_id)));
      const accEdge = edges.find((e) => e.uniprot_accession);
      // Prefer the row's own identity (carried by the manual/edit prefill — user_provided mode has
      // no edges); fall back to the edge for a computed row. Symmetric with Stage 4, which reads
      // the accession straight off the row.
      return {
        target_id: t.target_id,
        gene_symbol: t.canonical_name ?? t.target_id,
        uniprot_accession: t.uniprot_accession ?? accEdge?.uniprot_accession ?? null,
        source_url: t.source_url ?? accEdge?.source_url ?? null,
        methods,
        compound_count: compoundIds.length,
        source_compounds: compoundIds.map((cid) => nameById.get(cid) ?? cid),
        tag: t.tag,
      };
    });
}

const S3_CSV_HEADER = "gene_symbol,uniprot_accession,prediction_method,source_compounds,source_url";

/**
 * CSV keyed on gene symbol + UniProt accession + method + source compounds + source_url.
 * NEVER includes a UUID column (hard requirement). Values stay RAW (no display rounding).
 */
function buildS3CsvRows(rows: TargetRow[]): unknown[][] {
  return rows.map((r) => [
    r.gene_symbol,
    r.uniprot_accession,
    r.methods.map(methodLabel).join("; "),
    r.source_compounds.join("; "),
    r.source_url,
  ]);
}

function tagBadge(tag: TargetTag): React.ReactElement | null {
  if (tag === "user-added") {
    return (
      <Badge variant="secondary" className="text-[10px]">
        user-added
      </Badge>
    );
  }
  if (tag === "user-removed") {
    return (
      <Badge variant="destructive" className="text-[10px]">
        user-removed
      </Badge>
    );
  }
  return null;
}

// ---------------------------------------------------------------------------
// Stage3View
// ---------------------------------------------------------------------------

export function Stage3View({ data }: { data: AnalysisRead }) {
  const stage3 = data.stage_results?.["3"] as Stage3Result | undefined;
  const stage2 = data.stage_results?.["2"] as { passed?: Stage2Passed[] } | undefined;
  const stageState = (data as { stage_state?: Record<string, string> }).stage_state?.["3"];
  const targetParams = (data.parameters as Record<string, unknown> | undefined)?.target as
    | Record<string, number | boolean>
    | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  const qc = useQueryClient();

  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (error) => notifyError(error as Problem),
  });

  const redo = useMutation({
    mutationFn: (changed: Record<string, number | boolean | string>) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 3 },
        body: { parameters: { "3": changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo("Re-running from step 3");
    },
    onError: (error) => notifyError(error as Problem),
  });

  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: data.analysis_id, stage: 3 }, body }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (error) => notifyError(error as Problem),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  const currentTargetIds = new Set((stage3?.targets ?? []).map((t) => t.target_id));
  const { alreadyInRun, handleAdd: handleAddTargets } = useAddWithDedup<ResolvedTarget>({
    currentIds: currentTargetIds,
    getId: (r) => r.target_id,
    onAddIds: (ids) => edit.mutate({ add: ids, remove: [] }),
  });

  const passed = useMemo(() => stage2?.passed ?? [], [stage2]);
  const nameById = useMemo(
    () => new Map(passed.map((c) => [c.compound_id, c.canonical_name])),
    [passed],
  );

  const targetRows = useMemo(
    () => (stage3 ? buildTargetRows(stage3, nameById) : []),
    [stage3, nameById],
  );
  const csvRows = useMemo(() => buildS3CsvRows(targetRows), [targetRows]);

  if (!stage3) return null;

  // not_applicable → greyed note.
  if (stageState === "not_applicable") {
    return (
      <section className="stage-view stage-view--na" aria-disabled>
        <h2>Step 3: Target Identification</h2>
        <p className={cn("text-sm", "[color:var(--hf-fg-3)]")}>Not applicable for this run.</p>
      </section>
    );
  }

  // Entry-mode "manual targets" plant input hides compounds/coverage/STP (no compounds exist).
  // Key this ONLY on the entry-mode stage_state — NOT on stage3.state, which the durable edit
  // layer flips to "user_provided" merely because the computed set was edited (a manual add or
  // an STP import). Conflating the two would make the STP dialog and coverage table vanish after
  // the first edit, breaking the recall-mitigation loop.
  const isUserProvided = stageState === "user_provided";

  // Per-source edge counts (tallied over compound_targets).
  const sourceCounts = stage3.compound_targets.reduce<Record<string, number>>((acc, e) => {
    acc[e.prediction_method] = (acc[e.prediction_method] ?? 0) + 1;
    return acc;
  }, {});

  // Pagination over the target rows.
  const effectivePageSize = pageSize === "all" ? Math.max(1, targetRows.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(targetRows.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visibleRows = targetRows.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  // Effective target count for cap enforcement (exclude user-removed).
  const effectiveCount = stage3.targets.filter((t) => t.tag !== "user-removed").length;

  const stpCompounds: StpCompound[] = passed.map((c) => ({
    compound_id: c.compound_id,
    canonical_name: c.canonical_name,
    smiles: c.smiles ?? null,
  }));

  // Per-target column definitions — SAME columns + order as the prior table, plus the delete action.
  const targetColumns: ColumnDef<TargetRow>[] = [
    {
      id: "gene_symbol",
      header: "Gene symbol",
      cell: ({ row }) => row.original.gene_symbol,
    },
    {
      id: "uniprot",
      header: "UniProt",
      cell: ({ row }) => {
        const r = row.original;
        if (!r.uniprot_accession) return "—";
        return r.source_url ? (
          <a
            href={r.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[color:var(--hf-accent)] underline underline-offset-2"
          >
            {r.uniprot_accession}
          </a>
        ) : (
          r.uniprot_accession
        );
      },
    },
    {
      id: "evidence",
      header: "Evidence",
      cell: ({ row }) =>
        row.original.methods.length > 0 ? row.original.methods.map(methodLabel).join(", ") : "—",
    },
    {
      id: "compounds",
      header: "# compounds",
      cell: ({ row }) => row.original.compound_count,
    },
    {
      id: "tag",
      header: "",
      cell: ({ row }) => tagBadge(row.original.tag),
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`Remove ${row.original.gene_symbol}`}
          onClick={() => edit.mutate({ add: [], remove: [row.original.target_id] })}
          disabled={atMinEntities(effectiveCount)}
          title={
            atMinEntities(effectiveCount)
              ? "Keep at least one target before removing another."
              : undefined
          }
        >
          ✕
        </Button>
      ),
    },
  ];

  // Per-compound coverage rows + columns (0-coverage rows always visible).
  const coverageRows: CoverageRow[] = Object.entries(stage3.per_compound).map(
    ([compoundId, info]) => ({
      compound_id: compoundId,
      compound: nameById.get(compoundId) ?? compoundId,
      coverage: info.coverage,
    }),
  );

  const coverageColumns: ColumnDef<CoverageRow>[] = [
    {
      id: "compound",
      header: "Compound",
      cell: ({ row }) => (
        <span className={row.original.coverage === 0 ? "[color:var(--hf-fg-3)]" : undefined}>
          {row.original.compound}
        </span>
      ),
    },
    {
      id: "coverage",
      header: "Targets",
      cell: ({ row }) => row.original.coverage,
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      {/* Editorial header */}
      <div className="flex flex-col gap-1">
        <Eyebrow>Step 3</Eyebrow>
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="hf-heading-serif">
            Step 3: Target Identification
            {isUserProvided && (
              <Badge variant="outline" className="ml-2 align-middle text-xs font-normal">
                Provided by you
              </Badge>
            )}
          </h2>
        </div>
        <StageEntityContext data={data} side="plant" />
      </div>

      <StageDataSources stage={3} userProvided={isUserProvided} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage3.count} targets`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{stage3.count}</span>
          <span className="text-muted-foreground text-xs">targets</span>
        </div>
        {!isUserProvided && (
          <>
            <div
              className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
              aria-label={`${formatSig(stage3.coverage_pct)}% coverage`}
            >
              <span className="hf-num text-2xl font-semibold tabular-nums">
                {formatSig(stage3.coverage_pct)}%
              </span>
              <span className="text-muted-foreground text-xs">coverage</span>
            </div>
            <div
              className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
              aria-label={`${sourceCounts.chembl_bioactivity ?? 0} ChEMBL target links`}
            >
              <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
                {sourceCounts.chembl_bioactivity ?? 0}
              </span>
              <span className="text-muted-foreground text-xs">ChEMBL</span>
            </div>
            <div
              className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
              aria-label={`${sourceCounts.pubchem_bioassay ?? 0} PubChem BioAssay target links`}
            >
              <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
                {sourceCounts.pubchem_bioassay ?? 0}
              </span>
              <span className="text-muted-foreground text-xs">PubChem BioAssay</span>
            </div>
          </>
        )}
      </div>

      {/* Targets table card */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="t3-page-size" className="text-muted-foreground text-sm">
                Rows per page
              </label>
              <select
                id="t3-page-size"
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
              header={S3_CSV_HEADER}
              rows={csvRows}
              filename="targets.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="px-0">
          {/* Targets table */}
          <div className="table-wrapper">
            <DataTable columns={targetColumns} data={visibleRows} />
          </div>
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

      {/* Per-compound coverage — skipped for user_provided (no compounds) */}
      {!isUserProvided && (
        <Card>
          <CardHeader>
            <h3 className="text-sm font-semibold">Per-compound coverage</h3>
          </CardHeader>
          <CardContent className="coverage-table px-0">
            <DataTable columns={coverageColumns} data={coverageRows} />
          </CardContent>
        </Card>
      )}

      {/* Target add (the table above owns remove) */}
      <EntityAddControl current={effectiveCount} cap={MAX_TARGETS}>
        <TargetValidateBox label="Add targets" onResolved={handleAddTargets} showAddButton />
      </EntityAddControl>

      {/* Already-in-run note */}
      <AlreadyInRunNote
        labels={alreadyInRun.map((t) => t.gene_symbol ?? t.uniprot_accession ?? t.target_id)}
      />

      {/* Param panel */}
      {targetParams && !isUserProvided && (
        <ParamPanel
          params={targetParams}
          meta={TARGET_PARAMS}
          numericKeys={TARGET_NUMERIC_PARAMS}
          booleanKeys={[]}
          title="Target parameters"
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {/* STP paste-back — computed runs only */}
      {!isUserProvided && (
        <StpDialog
          compounds={stpCompounds}
          perCompound={stage3.per_compound}
          existingTargetIds={stage3.targets
            .filter((t) => t.tag !== "user-removed")
            .map((t) => t.target_id)}
          onAddTargets={handleAddTargets}
        />
      )}

      {/* Approval */}
      {(stage3 as { stale?: boolean }).stale && rerunFrom != null && (
        <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
      )}
      <ApprovalBar
        stage={3}
        status={data.status}
        currentStage={data.current_stage}
        disabled={stage3.count === 0 || anyStale}
        disabledReason={
          anyStale
            ? "Run the updated step before continuing."
            : "No targets found. Adjust the settings or add one to continue."
        }
        pending={advance.isPending}
        onApprove={() => advance.mutate()}
      />

      {/* Footer */}
      <p className="text-muted-foreground text-sm">
        Targets: ChEMBL + PubChem BioAssay. Human targets only (9606).
      </p>
    </section>
  );
}
