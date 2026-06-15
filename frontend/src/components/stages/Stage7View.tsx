/**
 * Stage7View — Stage 7 hub-gene ranking (networkx centralities + Maximal Clique Centrality (MCC)).
 *
 * Param-bearing (`hub_genes`: top_n). Renders summary cards, the ranked hub table (rank, gene,
 * MCC, and the four individual centralities for transparency) with per-row UniProt links + CSV,
 * the param panel (Redo via reset-from/7), the StageDataSources footer, the ApprovalBar, a
 * `network_too_small` notice, and the StaleNotice.
 */

import { useMemo, useState } from "react";
import { useCsvBlobUrl } from "../../lib/csv";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { formatSig } from "../../lib/format";
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis, resetFrom } from "../../api/sdk.gen";
import {
  HUB_GENES_BOOLEAN_PARAMS,
  HUB_GENES_NUMERIC_PARAMS,
  HUB_GENES_PARAMS,
} from "../../contract";
import { useStaleState } from "../../hooks/useStaleState";
import { exportArtifactUrl } from "../../lib/exportUrl";
import { ApprovalBar } from "./ApprovalBar";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StaleNotice } from "./StaleNotice";

// ---------------------------------------------------------------------------
// Local types for the Stage 7 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type Hub = {
  rank: number;
  target_id: string | null;
  gene_symbol: string;
  degree: number;
  betweenness: number;
  closeness: number;
  eigenvector: number;
  mcc: number;
  source_url: string | null;
};

type Stage7Result = {
  state: "computed";
  hubs: Hub[];
  ranking_metric: string;
  node_count: number;
  top_n: number;
  count: number;
  flags?: string[];
  stale?: boolean;
};

type HubParams = Record<string, number | boolean | string>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 20, 50] as const;

const S7_CSV_HEADER = "rank,gene_symbol,mcc,degree,betweenness,closeness,eigenvector,source_url";

function buildS7CsvRows(hubs: Hub[]): unknown[][] {
  return hubs.map((h) => [
    h.rank,
    h.gene_symbol,
    h.mcc,
    h.degree,
    h.betweenness,
    h.closeness,
    h.eigenvector,
    h.source_url,
  ]);
}

// ---------------------------------------------------------------------------
// Stage7View
// ---------------------------------------------------------------------------

export function Stage7View({ data }: { data: AnalysisRead }) {
  const stage7 = data.stage_results?.["7"] as Stage7Result | undefined;
  const hubParams = (data.parameters as Record<string, unknown> | undefined)?.hub_genes as
    | HubParams
    | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const redo = useMutation({
    mutationFn: (changed: HubParams) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 7 },
        body: { parameters: { "7": changed } },
      }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  const hubs = useMemo(() => stage7?.hubs ?? [], [stage7]);
  const csvHref = useCsvBlobUrl(S7_CSV_HEADER, buildS7CsvRows(hubs));

  if (!stage7) return null;

  const effectivePageSize = pageSize === "all" ? Math.max(1, hubs.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(hubs.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visible = hubs.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  const tooSmall = (stage7.flags ?? []).includes("network_too_small");
  const stale = stage7.stale === true;
  const isComplete = data.status === "complete";

  return (
    <section className="stage-view stage-view--7">
      <h2>Step 7 — Hub Genes</h2>
      <StageDataSources stage={7} />

      {/* Summary cards */}
      <div className="stage-summary">
        <div className="summary-card" aria-label={`${stage7.node_count} nodes`}>
          <span className="summary-card__value">{stage7.node_count}</span>
          <span className="summary-card__label">network nodes</span>
        </div>
        <div className="summary-card" aria-label={`${hubs.length} hubs`}>
          <span className="summary-card__value">{hubs.length}</span>
          <span className="summary-card__label">hubs reported</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`metric ${stage7.ranking_metric}`}
        >
          <span className="summary-card__value">{stage7.ranking_metric}</span>
          <span className="summary-card__label">ranking metric</span>
        </div>
      </div>

      {tooSmall && (
        <p className="hf-muted" role="status">
          The network is small or sparse — centrality ranking is unreliable on trivial topology.
        </p>
      )}

      {isComplete && (
        <img
          className="hf-stage-chart"
          alt="Top hub genes"
          src={exportArtifactUrl(data.analysis_id, "stage7_hub_bar.png")}
          onError={(e) => {
            e.currentTarget.style.display = "none";
          }}
        />
      )}

      {/* Table controls */}
      <div className="table-controls">
        <label htmlFor="t7-page-size">Rows per page</label>
        <select
          id="t7-page-size"
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
          download="hub-genes.csv"
          className="hf-btn hf-btn-ghost"
          aria-label="Download CSV"
        >
          Download CSV
        </a>
      </div>

      {/* Hub-ranking table */}
      <div className="table-wrapper">
        <table className="hf-table">
          <thead>
            <tr>
              <th>Rank</th>
              <th>Gene</th>
              <th>MCC</th>
              <th>Degree</th>
              <th>Betweenness</th>
              <th>Closeness</th>
              <th>Eigenvector</th>
            </tr>
          </thead>
          <tbody>
            {visible.map((h) => (
              <tr key={`${h.gene_symbol}-${h.rank}`}>
                <td>{h.rank}</td>
                <td>
                  {h.source_url ? (
                    <a href={h.source_url} target="_blank" rel="noreferrer">
                      {h.gene_symbol}
                    </a>
                  ) : (
                    h.gene_symbol
                  )}
                </td>
                <td>{h.mcc}</td>
                <td>{formatSig(h.degree)}</td>
                <td>{formatSig(h.betweenness)}</td>
                <td>{formatSig(h.closeness)}</td>
                <td>{formatSig(h.eigenvector)}</td>
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

      {/* Hub-ranking param panel */}
      {hubParams && (
        <ParamPanel
          params={hubParams}
          meta={HUB_GENES_PARAMS}
          numericKeys={HUB_GENES_NUMERIC_PARAMS}
          booleanKeys={HUB_GENES_BOOLEAN_PARAMS}
          selectKeys={[]}
          title="Hub-ranking parameters"
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {stale && rerunFrom != null && (
        <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
      )}
      <ApprovalBar
        stage={7}
        status={data.status}
        currentStage={data.current_stage}
        disabled={anyStale}
        disabledReason="Re-run the out-of-date step before continuing."
        onApprove={() => advance.mutate()}
      />

      <footer className="stage-footer hf-muted">
        <p>
          Ranking: Maximal Clique Centrality (MCC, Chin 2014) on the undirected STRING PPI. Degree,
          betweenness, closeness, and eigenvector centrality (networkx) are reported per target for
          transparency. Human only (species 9606).
        </p>
      </footer>
    </section>
  );
}
