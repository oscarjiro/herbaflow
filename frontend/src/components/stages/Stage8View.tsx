/**
 * Stage8View — Stage 8 functional enrichment (g:Profiler, GO + KEGG). Terminal stage.
 *
 * Param-bearing (`enrichment`: significance_threshold, min_term_size, correction, no_iea,
 * sources). Renders summary
 * cards (input/background gene counts + the shown custom background source), the enriched-terms
 * table + CSV, the param panel (Redo via reset-from/8), honest-null + degraded notices, the
 * data-sources footer, and the ApprovalBar (approving completes the run).
 */

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { formatSig } from "../../lib/format";
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis, resetFrom } from "../../api/sdk.gen";
import {
  ENRICHMENT_ARRAY_PARAMS,
  ENRICHMENT_BOOLEAN_PARAMS,
  ENRICHMENT_NUMERIC_PARAMS,
  ENRICHMENT_PARAMS,
  ENRICHMENT_SELECT_PARAMS,
} from "../../contract";
import { useStaleState } from "../../hooks/useStaleState";
import { exportArtifactUrl } from "../../lib/exportUrl";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { Eyebrow } from "@/components/ui/editorial";
import { ApprovalBar } from "./ApprovalBar";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StaleNotice } from "./StaleNotice";

// ---------------------------------------------------------------------------
// Local types for the Stage 8 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type Term = {
  source: string;
  term_id: string;
  name: string;
  p_value: number;
  term_size: number;
  query_size: number;
  intersection_size: number;
  intersection: string[];
};

type Stage8Result = {
  state: "computed";
  terms: Term[];
  input_gene_count: number;
  background_gene_count: number;
  background_source: string;
  correction: string;
  significance_threshold: number;
  min_term_size: number;
  sources: string[];
  degraded: boolean;
  count: number;
  flags?: string[];
  stale?: boolean;
};

type EnrichmentParams = Record<string, number | boolean | string | string[]>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 20, 50] as const;

const S8_CSV_HEADER = "source,term_id,name,p_value,term_size,intersection_size,intersection";

function buildS8CsvRows(terms: Term[]): unknown[][] {
  return terms.map((t) => [
    t.source,
    t.term_id,
    t.name,
    t.p_value,
    t.term_size,
    t.intersection_size,
    (t.intersection ?? []).join(" "),
  ]);
}

// ---------------------------------------------------------------------------
// Stage8View
// ---------------------------------------------------------------------------

export function Stage8View({ data }: { data: AnalysisRead }) {
  const stage8 = data.stage_results?.["8"] as Stage8Result | undefined;
  const enrichParams = (data.parameters as Record<string, unknown> | undefined)?.enrichment as
    | EnrichmentParams
    | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const redo = useMutation({
    mutationFn: (changed: EnrichmentParams) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 8 },
        body: { parameters: { "8": changed } },
      }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  const terms = useMemo(() => stage8?.terms ?? [], [stage8]);
  const csvRows = useMemo(() => buildS8CsvRows(terms), [terms]);

  if (!stage8) return null;

  const effectivePageSize = pageSize === "all" ? Math.max(1, terms.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(terms.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visible = terms.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  const stale = stage8.stale === true;
  const isComplete = data.status === "complete";

  // Column definitions — SAME columns + order as the prior <table>
  const columns: ColumnDef<Term>[] = [
    {
      id: "source",
      header: "Source",
      cell: ({ row }) => row.original.source,
    },
    {
      id: "term",
      header: "Term",
      cell: ({ row }) => row.original.term_id,
    },
    {
      id: "name",
      header: "Name",
      cell: ({ row }) => row.original.name,
    },
    {
      id: "corrected_p",
      header: "Corrected p",
      cell: ({ row }) => formatSig(row.original.p_value),
    },
    {
      id: "term_size",
      header: "Term size",
      cell: ({ row }) => row.original.term_size,
    },
    {
      id: "overlap",
      header: "Overlap",
      cell: ({ row }) => row.original.intersection_size,
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      {/* Editorial header */}
      <div className="flex flex-col gap-1">
        <Eyebrow>Step 8</Eyebrow>
        <h2 className="hf-heading-serif">Step 8: Functional Enrichment</h2>
      </div>

      <StageDataSources stage={8} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage8.count} terms`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{stage8.count}</span>
          <span className="text-muted-foreground text-xs">enriched terms</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage8.input_gene_count} query genes`}
        >
          <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
            {stage8.input_gene_count}
          </span>
          <span className="text-muted-foreground text-xs">query genes</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage8.background_gene_count} background genes`}
        >
          <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
            {stage8.background_gene_count}
          </span>
          <span className="text-muted-foreground text-xs">background genes</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`correction ${stage8.correction}`}
        >
          <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
            {stage8.correction}
          </span>
          <span className="text-muted-foreground text-xs">correction</span>
        </div>
      </div>

      <p className="text-muted-foreground text-sm">
        Background: {stage8.background_source.replace(/_/g, " ")} ({stage8.background_gene_count}{" "}
        genes). Custom universe, not the whole genome.
      </p>

      {stage8.degraded && (
        <div role="status">
          <Badge variant="destructive">
            g:Profiler was unavailable. Enrichment was skipped, but the run still completed.
          </Badge>
        </div>
      )}

      {!stage8.degraded && stage8.count === 0 && (
        <p className="text-muted-foreground text-sm" role="status">
          No terms survived correction at this threshold. The gene set may be small or widely
          distributed.
        </p>
      )}

      {terms.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-3">
              <div className="flex items-center gap-2">
                <label htmlFor="t8-page-size" className="text-muted-foreground text-sm">
                  Rows per page
                </label>
                <select
                  id="t8-page-size"
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
                header={S8_CSV_HEADER}
                rows={csvRows}
                filename="enrichment.csv"
                label="Download CSV"
              />
            </div>
          </CardHeader>
          <CardContent className="px-0">
            <DataTable columns={columns} data={visible} />
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
      )}

      {/* Per-category enrichment chart images (complete-only, onError-hidden) */}
      {isComplete &&
        (
          [
            ["BP", "Biological Process"],
            ["MF", "Molecular Function"],
            ["CC", "Cellular Component"],
            ["KEGG", "KEGG Pathway"],
            ["REAC", "Reactome Pathway"],
            ["WP", "WikiPathways"],
          ] as [string, string][]
        ).map(([cat, label]) => (
          <img
            key={cat}
            className="border-hf-border max-w-full rounded-[var(--radius-3)] border"
            alt={`${label} enrichment`}
            src={exportArtifactUrl(data.analysis_id, `stage8_enrichment_${cat}.png`)}
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
        ))}

      {/* Enrichment param panel */}
      {enrichParams && (
        <ParamPanel
          params={enrichParams}
          meta={ENRICHMENT_PARAMS}
          numericKeys={ENRICHMENT_NUMERIC_PARAMS}
          booleanKeys={ENRICHMENT_BOOLEAN_PARAMS}
          selectKeys={ENRICHMENT_SELECT_PARAMS}
          arrayKeys={ENRICHMENT_ARRAY_PARAMS}
          title="Enrichment parameters"
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {stale && rerunFrom != null && (
        <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
      )}

      {isComplete ? (
        <p className="text-muted-foreground text-sm" role="status">
          Analysis complete. All eight steps finished.
        </p>
      ) : (
        <ApprovalBar
          stage={8}
          status={data.status}
          currentStage={data.current_stage}
          disabled={anyStale}
          disabledReason="Run the updated step before continuing."
          onApprove={() => advance.mutate()}
        />
      )}

      <footer className="text-muted-foreground text-sm">
        <p>
          Enrichment: g:Profiler (GO BP/MF/CC + KEGG), cumulative hypergeometric, custom background
          = the compound-target universe. Human only (species 9606).
        </p>
      </footer>
    </section>
  );
}
