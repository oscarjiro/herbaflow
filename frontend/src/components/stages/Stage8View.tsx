/**
 * Stage8View — Stage 8 functional enrichment (g:Profiler, GO + KEGG). Terminal stage.
 *
 * Param-bearing (`enrichment`: significance_threshold, min_term_size, correction, no_iea;
 * `sources` stays frozen — the multi-select control is deferred to Phase 5). Renders summary
 * cards (input/background gene counts + the shown custom background source), the enriched-terms
 * table + CSV, the param panel (Redo via reset-from/8), honest-null + degraded notices, the
 * data-sources footer, and the ApprovalBar (approving completes the run).
 */

import { useMemo, useState } from "react";
import { useCsvBlobUrl } from "../../lib/csv";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis, resetFrom } from "../../api/sdk.gen";
import {
  ENRICHMENT_BOOLEAN_PARAMS,
  ENRICHMENT_NUMERIC_PARAMS,
  ENRICHMENT_PARAMS,
  ENRICHMENT_SELECT_PARAMS,
} from "../../contract";
import { useStaleState } from "../../hooks/useStaleState";
import { exportArtifactUrl } from "../../lib/exportUrl";
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

type EnrichmentParams = Record<string, number | boolean | string>;

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
  const csvHref = useCsvBlobUrl(S8_CSV_HEADER, buildS8CsvRows(terms));

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

  return (
    <section className="stage-view stage-view--8">
      <h2>Step 8 — Functional Enrichment</h2>
      <StageDataSources stage={8} />

      {/* Summary cards */}
      <div className="stage-summary">
        <div className="summary-card" aria-label={`${stage8.count} terms`}>
          <span className="summary-card__value">{stage8.count}</span>
          <span className="summary-card__label">enriched terms</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`${stage8.input_gene_count} query genes`}
        >
          <span className="summary-card__value">{stage8.input_gene_count}</span>
          <span className="summary-card__label">query genes</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`${stage8.background_gene_count} background genes`}
        >
          <span className="summary-card__value">{stage8.background_gene_count}</span>
          <span className="summary-card__label">background genes</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`correction ${stage8.correction}`}
        >
          <span className="summary-card__value">{stage8.correction}</span>
          <span className="summary-card__label">correction</span>
        </div>
      </div>

      <p className="hf-muted">
        Background: {stage8.background_source.replace(/_/g, " ")} ({stage8.background_gene_count}{" "}
        genes) — the methodologically-correct custom universe (not the whole genome).
      </p>

      {stage8.degraded && (
        <p className="hf-badge hf-badge--warn" role="status">
          g:Profiler was unavailable — enrichment was skipped, but the run still completed.
        </p>
      )}

      {!stage8.degraded && stage8.count === 0 && (
        <p className="hf-muted" role="status">
          No terms survived correction at this threshold — an honest null for a small or
          well-dispersed gene set.
        </p>
      )}

      {terms.length > 0 && (
        <>
          {/* Table controls */}
          <div className="table-controls">
            <label htmlFor="t8-page-size">Rows per page</label>
            <select
              id="t8-page-size"
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
              download="enrichment.csv"
              className="hf-btn hf-btn-ghost"
              aria-label="Download CSV"
            >
              Download CSV
            </a>
          </div>

          {/* Enriched-terms table */}
          <div className="table-wrapper">
            <table className="hf-table">
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Term</th>
                  <th>Name</th>
                  <th>Corrected p</th>
                  <th>Term size</th>
                  <th>Overlap</th>
                </tr>
              </thead>
              <tbody>
                {visible.map((t) => (
                  <tr key={t.term_id}>
                    <td>{t.source}</td>
                    <td>{t.term_id}</td>
                    <td>{t.name}</td>
                    <td>{t.p_value.toExponential(2)}</td>
                    <td>{t.term_size}</td>
                    <td>{t.intersection_size}</td>
                  </tr>
                ))}
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
        </>
      )}

      {isComplete &&
        (
          [
            ["BP", "Biological process enrichment"],
            ["MF", "Molecular function enrichment"],
            ["CC", "Cellular component enrichment"],
            ["KEGG", "KEGG pathway enrichment"],
            ["REAC", "Reactome pathway enrichment"],
            ["WP", "WikiPathways enrichment"],
          ] as [string, string][]
        ).map(([cat, altText]) => (
          <img
            key={cat}
            className="hf-stage-chart"
            alt={altText}
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
          title="Enrichment parameters"
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {stale && rerunFrom != null && (
        <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
      )}

      {isComplete ? (
        <p className="hf-badge hf-badge--ok" role="status">
          Pipeline complete — all eight stages finished.
        </p>
      ) : (
        <ApprovalBar
          stage={8}
          status={data.status}
          currentStage={data.current_stage}
          disabled={anyStale}
          disabledReason="Re-run the out-of-date step before continuing."
          onApprove={() => advance.mutate()}
        />
      )}

      <footer className="stage-footer hf-muted">
        <p>
          Enrichment: g:Profiler (GO BP/MF/CC + KEGG), cumulative hypergeometric, custom background
          = the compound-target universe. Human only (species 9606).
        </p>
      </footer>
    </section>
  );
}
