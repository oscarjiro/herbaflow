/**
 * Stage5View — overlap of Stage 3 (compound→target) ∩ Stage 4 (disease→target).
 *
 * Stage 5 has NO parameters and is NOT an entity stage. It is a read-only view:
 *  - Summary cards: overlap count + compound-side / disease-side set sizes
 *  - Overlap table: gene symbol, UniProt accession (linked), opentargets_score; paginated
 *  - CSV download of the overlap rows
 *  - StageDataSources footer
 *  - ApprovalBar (self-gates to stage 5 being the current awaiting stage)
 *
 * No param panel, no Redo, no entity add/remove, no TargetValidateBox.
 */

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { formatSig } from "../../lib/format";
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError } from "../../lib/toast";
import { useStaleState } from "../../hooks/useStaleState";
import { exportArtifactUrl } from "../../lib/exportUrl";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { DataTable } from "@/components/ui/DataTable";
import { Eyebrow } from "@/components/ui/editorial";
import { ApprovalBar } from "./ApprovalBar";
import { StageDataSources } from "./StageDataSources";
import { StaleNotice } from "./StaleNotice";

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

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 20, 50] as const;

const S5_CSV_HEADER = "gene_symbol,uniprot_accession,opentargets_score,source_url";

function buildS5CsvRows(rows: OverlapRow[]): unknown[][] {
  return rows.map((r) => {
    const acc = r.uniprot_accession;
    const sourceUrl = acc ? `https://www.uniprot.org/uniprotkb/${acc}/entry` : null;
    return [r.gene_symbol, acc, r.opentargets_score, sourceUrl];
  });
}

// ---------------------------------------------------------------------------
// Stage5View
// ---------------------------------------------------------------------------

export function Stage5View({ data }: { data: AnalysisRead }) {
  const stage5 = data.stage_results?.["5"] as Stage5Result | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);
  const isComplete = data.status === "complete";

  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (error) => notifyError(error as Problem),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  const csvRows = useMemo(() => buildS5CsvRows(stage5?.overlap ?? []), [stage5]);

  if (!stage5) return null;

  // Pagination
  const rows = stage5.overlap;
  const effectivePageSize = pageSize === "all" ? Math.max(1, rows.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(rows.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visibleRows = rows.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  // Column definitions — SAME columns + order as the prior <table>
  const columns: ColumnDef<OverlapRow>[] = [
    {
      id: "gene_symbol",
      header: "Gene symbol",
      cell: ({ row }) => row.original.gene_symbol ?? "—",
    },
    {
      id: "uniprot",
      header: "UniProt",
      cell: ({ row }) => {
        const acc = row.original.uniprot_accession;
        if (!acc) return "—";
        const sourceUrl = `https://www.uniprot.org/uniprotkb/${acc}/entry`;
        return (
          <a
            href={sourceUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[color:var(--hf-accent)] underline underline-offset-2"
          >
            {acc}
          </a>
        );
      },
    },
    {
      id: "opentargets_score",
      header: "Open Targets score",
      cell: ({ row }) => formatSig(row.original.opentargets_score),
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      {/* Editorial header */}
      <div className="flex flex-col gap-1">
        <Eyebrow>Step 5</Eyebrow>
        <h2 className="hf-heading-serif">Step 5: Target Overlap</h2>
      </div>

      <StageDataSources stage={5} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage5.count} overlap targets`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{stage5.count}</span>
          <span className="text-muted-foreground text-xs">overlap targets</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage5.compound_target_count} compound-side targets`}
        >
          <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
            {stage5.compound_target_count}
          </span>
          <span className="text-muted-foreground text-xs">compound-side targets</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage5.disease_target_count} disease-side targets`}
        >
          <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
            {stage5.disease_target_count}
          </span>
          <span className="text-muted-foreground text-xs">disease-side targets</span>
        </div>
      </div>

      {/* Venn diagram image (complete-only, onError-hidden) */}
      {isComplete && (
        <img
          className="border-hf-border max-w-full rounded-[var(--radius-3)] border"
          alt="Target overlap"
          src={exportArtifactUrl(data.analysis_id, "stage5_venn.png")}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
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
            <div className="flex items-center gap-2">
              <label htmlFor="t5-page-size" className="text-muted-foreground text-sm">
                Rows per page
              </label>
              <select
                id="t5-page-size"
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
              header={S5_CSV_HEADER}
              rows={csvRows}
              filename="overlap-targets.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="px-0">
          <DataTable columns={columns} data={visibleRows} />
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

      {/* Stale notice + approval */}
      {(stage5 as { stale?: boolean }).stale && rerunFrom != null && (
        <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
      )}
      <ApprovalBar
        stage={5}
        status={data.status}
        currentStage={data.current_stage}
        disabled={stage5.count === 0 || anyStale}
        disabledReason={
          anyStale
            ? "Run the updated step before continuing."
            : "No overlap targets. Check Step 3 and Step 4 results."
        }
        onApprove={() => advance.mutate()}
      />
    </section>
  );
}
