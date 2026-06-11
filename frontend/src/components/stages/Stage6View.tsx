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
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis, resetFrom } from "../../api/sdk.gen";
import {
  PPI_BOOLEAN_PARAMS,
  PPI_NUMERIC_PARAMS,
  PPI_PARAMS,
  PPI_SELECT_PARAMS,
} from "../../contract";
import { useStaleState } from "../../hooks/useStaleState";
import { ApprovalBar } from "./ApprovalBar";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StaleNotice } from "./StaleNotice";

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

type PpiParams = Record<string, number | boolean | string>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 20, 50] as const;

function isBlocked(r: Stage6Result): r is Stage6Blocked {
  return (r as Stage6Blocked).blocked === true;
}

function escapeCsv(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
}

function buildCsv(edges: Stage6Edge[]): string {
  const header = "source,target,confidence";
  const body = edges
    .map((e) => [escapeCsv(e.source), escapeCsv(e.target), escapeCsv(e.confidence)].join(","))
    .join("\n");
  return `${header}\n${body}`;
}

// ---------------------------------------------------------------------------
// Stage6View
// ---------------------------------------------------------------------------

export function Stage6View({ data }: { data: AnalysisRead }) {
  const stage6 = data.stage_results?.["6"] as Stage6Result | undefined;
  const ppiParams = (data.parameters as Record<string, unknown> | undefined)?.ppi as
    | PpiParams
    | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const redo = useMutation({
    mutationFn: (changed: PpiParams) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 6 },
        body: { parameters: { "6": changed } },
      }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  const computed = stage6 && !isBlocked(stage6) ? stage6 : undefined;
  const edges = useMemo(() => computed?.edges ?? [], [computed]);
  const csvHref = useMemo(() => {
    const blob = new Blob([buildCsv(edges)], { type: "text/csv" });
    return URL.createObjectURL(blob);
  }, [edges]);

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

  const stale = (stage6 as { stale?: boolean }).stale === true;

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
    <section className="stage-view stage-view--6">
      <h2>Step 6 — PPI Network</h2>
      <StageDataSources stage={6} />

      {blocked ? (
        // ----- Overlap-too-large prompt -----
        <div className="stage-blocked" role="status">
          <p className="hf-badge hf-badge--warn">Overlap too large</p>
          <p>
            The overlap of {blocked.overlap_count} proteins exceeds the STRING ceiling of{" "}
            {blocked.max_proteins}. Building a network this large is unreliable, so it was not
            queried.
          </p>
          <p className="hf-muted">
            Either enable the top-N cap to proceed on the {blocked.max_proteins} highest-ranked
            proteins, or narrow the inputs upstream (raise the Stage 3 / Stage 4 thresholds, or
            tighten the overlap) and re-run.
          </p>
          <button
            type="button"
            className="hf-btn hf-btn-primary"
            disabled={redo.isPending}
            onClick={() => redo.mutate({ allow_top_n_cap: true })}
            aria-label="Enable top-N cap and Redo"
          >
            Enable top-N &amp; Redo
          </button>
        </div>
      ) : (
        computed && (
          <>
            {/* Summary cards */}
            <div className="stage-summary">
              <div className="summary-card" aria-label={`${computed.node_count} nodes`}>
                <span className="summary-card__value">{computed.node_count}</span>
                <span className="summary-card__label">nodes</span>
              </div>
              <div className="summary-card" aria-label={`${computed.edge_count} edges`}>
                <span className="summary-card__value">{computed.edge_count}</span>
                <span className="summary-card__label">edges</span>
              </div>
              <div
                className="summary-card summary-card--muted"
                aria-label={`min confidence ${computed.min_confidence}`}
              >
                <span className="summary-card__value">{computed.min_confidence}</span>
                <span className="summary-card__label">min confidence</span>
              </div>
              <div
                className="summary-card summary-card--muted"
                aria-label={`network type ${computed.network_type}`}
              >
                <span className="summary-card__value">{computed.network_type}</span>
                <span className="summary-card__label">network type</span>
              </div>
              <div
                className="summary-card summary-card--muted"
                aria-label={`${computed.unmapped.length} unmapped`}
              >
                <span className="summary-card__value">{computed.unmapped.length}</span>
                <span className="summary-card__label">unmapped</span>
              </div>
            </div>

            {computed.capped.applied && (
              <p className="hf-muted" role="status">
                Capped to the top {computed.capped.max_proteins} proteins by{" "}
                {computed.capped.ranked_by}.
              </p>
            )}

            {computed.edge_count === 0 && (
              <p className="hf-muted" role="status">
                No interactions among the overlap targets at this confidence floor.
              </p>
            )}

            {/* Table controls */}
            <div className="table-controls">
              <label htmlFor="t6-page-size">Rows per page</label>
              <select
                id="t6-page-size"
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
                download="ppi-edges.csv"
                className="hf-btn hf-btn-ghost"
                aria-label="Download CSV"
              >
                Download CSV
              </a>
            </div>

            {/* Edge-list table */}
            <div className="table-wrapper">
              <table className="hf-table">
                <thead>
                  <tr>
                    <th>Source</th>
                    <th>Target</th>
                    <th>Confidence</th>
                  </tr>
                </thead>
                <tbody>
                  {visibleEdges.map((edge, i) => (
                    <tr key={`${edge.source}-${edge.target}-${i}`}>
                      <td>{edge.source}</td>
                      <td>{edge.target}</td>
                      <td>{edge.confidence}</td>
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
        )
      )}

      {/* PPI param panel — always shown (raise the cap / change settings + Redo) */}
      {paramPanel}

      {stale && rerunFrom != null && (
        <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
      )}
      <ApprovalBar
        stage={6}
        status={data.status}
        currentStage={data.current_stage}
        disabled={Boolean(blocked) || (computed?.node_count ?? 0) === 0 || anyStale}
        disabledReason={
          anyStale
            ? "Re-run the out-of-date step before continuing."
            : blocked
              ? "Overlap too large — enable the top-N cap and Redo, or narrow the inputs."
              : "No PPI nodes — adjust the parameters and Redo, or narrow the inputs."
        }
        onApprove={() => advance.mutate()}
      />

      <footer className="stage-footer hf-muted">
        <p>Protein interactions: STRING. Human only (species 9606).</p>
      </footer>
    </section>
  );
}
