/**
 * Stage5View — overlap of Stage 3 (compound→target) ∩ Stage 4 (disease→target).
 *
 * Stage 5 has NO parameters and is NOT an entity stage. It is a read-only view:
 *  - Summary cards: overlap count, Jaccard index, p-value, and a significant/not-significant badge
 *  - Overlap table: gene symbol, UniProt accession (linked), opentargets_score; paginated
 *  - CSV download of the overlap rows
 *  - StageDataSources footer
 *  - ApprovalBar (self-gates to stage 5 being the current awaiting stage)
 *
 * No param panel, no Redo, no entity add/remove, no TargetValidateBox.
 */

import { useState } from "react";
import { useCsvBlobUrl } from "../../lib/csv";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { formatSig } from "../../lib/format";
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis } from "../../api/sdk.gen";
import { useStaleState } from "../../hooks/useStaleState";
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

type HypergeometricResult = {
  background_n: number;
  K: number;
  n: number;
  k: number;
  p_value: number;
  alpha: number;
  significant: boolean;
};

type Stage5Result = {
  overlap: OverlapRow[];
  count: number;
  compound_target_count: number;
  disease_target_count: number;
  union_count: number;
  jaccard: number;
  hypergeometric: HypergeometricResult;
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

function formatPValue(p: number): string {
  if (p < 0.0001) return p.toExponential(2);
  return p.toFixed(4);
}

// ---------------------------------------------------------------------------
// Stage5View
// ---------------------------------------------------------------------------

export function Stage5View({ data }: { data: AnalysisRead }) {
  const stage5 = data.stage_results?.["5"] as Stage5Result | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  const csvHref = useCsvBlobUrl(S5_CSV_HEADER, buildS5CsvRows(stage5?.overlap ?? []));

  if (!stage5) return null;

  const { hypergeometric: hg } = stage5;
  const significant = hg.significant;
  const nonSigFlag = stage5.flags?.includes("non_significant_overlap") ?? false;

  // Pagination
  const rows = stage5.overlap;
  const effectivePageSize = pageSize === "all" ? Math.max(1, rows.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(rows.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visibleRows = rows.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  return (
    <section className="stage-view stage-view--5">
      <h2>Step 5 — Target Overlap</h2>
      <StageDataSources stage={5} />

      {/* Summary cards */}
      <div className="stage-summary">
        <div className="summary-card" aria-label={`${stage5.count} overlap targets`}>
          <span className="summary-card__value">{stage5.count}</span>
          <span className="summary-card__label">overlap targets</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`Jaccard ${stage5.jaccard.toFixed(3)}`}
        >
          <span className="summary-card__value">{stage5.jaccard.toFixed(3)}</span>
          <span className="summary-card__label">Jaccard index</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`p-value ${formatPValue(hg.p_value)}`}
        >
          <span className="summary-card__value">{formatPValue(hg.p_value)}</span>
          <span className="summary-card__label">p-value</span>
        </div>
        <div className="summary-card" aria-label={significant ? "significant" : "not significant"}>
          {significant && !nonSigFlag ? (
            <span className="hf-badge hf-badge--success">significant</span>
          ) : (
            <span className="hf-badge hf-badge--warn">not significant</span>
          )}
          <span className="summary-card__label">overlap</span>
        </div>
      </div>

      {stage5.count === 0 && (
        <p className="hf-muted" role="status">
          No targets overlap between compound–target and disease–target sets.
        </p>
      )}

      {/* Table controls */}
      <div className="table-controls">
        <label htmlFor="t5-page-size">Rows per page</label>
        <select
          id="t5-page-size"
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
        <a
          href={csvHref}
          download="overlap-targets.csv"
          className="hf-btn hf-btn-ghost"
          aria-label="Download CSV"
        >
          Download CSV
        </a>
      </div>

      {/* Overlap table */}
      <div className="table-wrapper">
        <table className="hf-table">
          <thead>
            <tr>
              <th>Gene symbol</th>
              <th>UniProt</th>
              <th>Open Targets score</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => {
              const sourceUrl = row.uniprot_accession
                ? `https://www.uniprot.org/uniprotkb/${row.uniprot_accession}/entry`
                : null;
              return (
                <tr key={row.target_id}>
                  <td>{row.gene_symbol ?? "—"}</td>
                  <td>
                    {row.uniprot_accession ? (
                      sourceUrl ? (
                        <a href={sourceUrl} target="_blank" rel="noopener noreferrer">
                          {row.uniprot_accession}
                        </a>
                      ) : (
                        row.uniprot_accession
                      )
                    ) : (
                      "—"
                    )}
                  </td>
                  <td>{formatSig(row.opentargets_score)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Pagination */}
      {pageSize !== "all" && totalPages > 1 && (
        <div className="pagination">
          <button
            className="hf-btn"
            disabled={currentPage === 0}
            onClick={() => setPage((p) => p - 1)}
          >
            Previous
          </button>
          <span>
            Page {currentPage + 1} / {totalPages}
          </span>
          <button
            className="hf-btn"
            disabled={currentPage >= totalPages - 1}
            onClick={() => setPage((p) => p + 1)}
          >
            Next
          </button>
        </div>
      )}

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
            ? "Re-run the out-of-date step before continuing."
            : "No overlap targets — check Stage 3 and Stage 4 results."
        }
        onApprove={() => advance.mutate()}
      />
    </section>
  );
}
