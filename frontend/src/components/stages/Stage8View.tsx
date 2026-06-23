/**
 * Stage8View — Stage 8 functional enrichment (g:Profiler, GO + KEGG). Terminal stage.
 *
 * Param-bearing (`enrichment`: significance_threshold, min_term_size, correction, no_iea,
 * sources). Renders summary
 * cards (input/background gene counts + the shown custom background source), the enriched-terms
 * table + CSV, the param panel (Redo via reset-from/8), honest-null + degraded notices, and the
 * data-sources footer.
 *
 * The stage header, ApprovalBar, and StaleNotice are owned by the StageView shell.
 */

import { useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { formatSig } from "../../lib/format";
import type { AnalysisRead } from "../../api/types.gen";
import { resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import {
  ENRICHMENT_ARRAY_PARAMS,
  ENRICHMENT_BOOLEAN_PARAMS,
  ENRICHMENT_NUMERIC_PARAMS,
  ENRICHMENT_PARAMS,
  ENRICHMENT_SELECT_PARAMS,
} from "../../contract";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { ChartFrame } from "@/components/charts/ChartFrame";
import { EnrichmentDotChart } from "@/components/charts/EnrichmentDotChart";
import { exportPlotlyAsPng } from "@/lib/chartExport";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";

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

  const qc = useQueryClient();
  const redo = useMutation({
    mutationFn: (changed: EnrichmentParams) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 8 },
        body: { parameters: { "8": changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo("Re-running from step 8");
    },
    onError: (error) => notifyError(error as Problem),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);
  const gdRef = useRef<HTMLElement | null>(null);

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

      {/* Interactive enrichment bubble chart (shown once terms exist) */}
      {terms.length > 0 && (
        <ChartFrame
          title="Pathway enrichment"
          filename="pathway_enrichment.png"
          onExport={async () => {
            if (gdRef.current)
              await exportPlotlyAsPng(gdRef.current, { filename: "pathway_enrichment.png" });
          }}
        >
          <EnrichmentDotChart
            terms={terms.map((t) => ({
              source: t.source,
              name: t.name,
              p_value: t.p_value,
              intersection_size: t.intersection_size,
            }))}
            onGraphDiv={(gd) => (gdRef.current = gd)}
          />
        </ChartFrame>
      )}

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

      <footer className="text-muted-foreground text-sm">
        <p>
          Enrichment: g:Profiler (GO BP/MF/CC + KEGG), cumulative hypergeometric, custom background
          = the compound-target universe. Human only (species 9606).
        </p>
      </footer>
    </section>
  );
}
