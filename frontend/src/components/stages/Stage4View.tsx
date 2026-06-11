/**
 * Stage4View — disease → target collection results (DB read of the seeded Open Targets snapshot).
 *
 * Renders:
 *  - Summary cards: target count + the applied min_score
 *  - Disease-targets table (one row per target): gene symbol, UniProt accession (linked), score,
 *    association type, edit tag badge; pagination (10/20/50/all); CSV keyed on
 *    gene_symbol + uniprot_accession + score + association_type + source_url (NEVER a UUID)
 *  - Target add/remove via EditableEntityList + TargetValidateBox (editStage stage 4)
 *  - ParamPanel (min_score) + Redo (resetFrom stage 4) and ApprovalBar — at count 0 the
 *    ApprovalBar is disabled with a reason (blocking-stop); recover via Redo or a manual add
 *  - Footer: "Open Targets (database snapshot); human targets only."
 *
 * State (stage_state["4"]):
 *  - "not_applicable" → greyed note
 *  - "user_provided"  → manual disease-targets (no score emphasis)
 *  - otherwise (computed) → full view
 * Manually-added targets appear in `targets` (tagged) but NOT in `disease_targets`, so their
 * score/UniProt columns render "—" (symmetric with Stage 3 user-added targets).
 */

import { useMemo, useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisRead, ResolvedTarget } from "../../api/types.gen";
import { advanceAnalysis, editStage, resetFrom } from "../../api/sdk.gen";
import {
  DISEASE_TARGETS_NUMERIC_PARAMS,
  DISEASE_TARGETS_PARAMS,
  MAX_TARGETS,
} from "../../contract";
import { useStaleState } from "../../hooks/useStaleState";
import { ApprovalBar } from "./ApprovalBar";
import { EditableEntityList } from "./EditableEntityList";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StaleNotice } from "./StaleNotice";
import { TargetValidateBox } from "../TargetValidateBox";

type TargetTag = "computed" | "user-added" | "user-removed" | string;

type TargetEntry = { target_id: string; canonical_name: string | null; tag: TargetTag };

type DiseaseTargetRow = {
  target_id: string;
  gene_symbol: string | null;
  uniprot_accession: string | null;
  score: number | null;
  association_type: string | null;
  source_url: string | null;
};

type Stage4Result = {
  targets: TargetEntry[];
  disease_targets: DiseaseTargetRow[];
  count: number;
  min_score_applied: number;
  state: string;
};

type Row = {
  target_id: string;
  gene_symbol: string;
  uniprot_accession: string | null;
  score: number | null;
  association_type: string | null;
  source_url: string | null;
  tag: TargetTag;
};

const PAGE_SIZES = [10, 20, 50] as const;

function buildRows(stage4: Stage4Result): Row[] {
  const byId = new Map(stage4.disease_targets.map((d) => [d.target_id, d]));
  return stage4.targets.map((t) => {
    const d = byId.get(t.target_id);
    return {
      target_id: t.target_id,
      gene_symbol: t.canonical_name ?? d?.gene_symbol ?? t.target_id,
      uniprot_accession: d?.uniprot_accession ?? null,
      score: d?.score ?? null,
      association_type: d?.association_type ?? null,
      source_url: d?.source_url ?? null,
      tag: t.tag,
    };
  });
}

function escapeCsv(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  return s.includes(",") || s.includes('"') || s.includes("\n") ? `"${s.replace(/"/g, '""')}"` : s;
}

function buildCsv(rows: Row[]): string {
  const header = "gene_symbol,uniprot_accession,score,association_type,source_url";
  const body = rows
    .map((r) =>
      [
        escapeCsv(r.gene_symbol),
        escapeCsv(r.uniprot_accession),
        escapeCsv(r.score),
        escapeCsv(r.association_type),
        escapeCsv(r.source_url),
      ].join(","),
    )
    .join("\n");
  return `${header}\n${body}`;
}

function tagBadge(tag: TargetTag): React.ReactElement | null {
  if (tag === "user-added") return <span className="hf-badge hf-badge--added">user-added</span>;
  if (tag === "user-removed")
    return <span className="hf-badge hf-badge--removed">user-removed</span>;
  return null;
}

export function Stage4View({ data }: { data: AnalysisRead }) {
  const stage4 = data.stage_results?.["4"] as Stage4Result | undefined;
  const stageState = (data as { stage_state?: Record<string, string> }).stage_state?.["4"];
  const dtParams = (data.parameters as Record<string, unknown> | undefined)?.disease_targets as
    | Record<string, number | boolean>
    | undefined;
  const { anyStale, rerunFrom } = useStaleState(data);

  const qc = useQueryClient();
  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const redo = useMutation({
    mutationFn: (changed: Record<string, number | boolean>) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 4 },
        body: { parameters: { "4": changed } },
      }),
    onSuccess: () => qc.invalidateQueries(),
  });
  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: data.analysis_id, stage: 4 }, body }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);
  const [alreadyInRun, setAlreadyInRun] = useState<ResolvedTarget[]>([]);

  const rows = useMemo(() => (stage4 ? buildRows(stage4) : []), [stage4]);
  const csvHref = useMemo(() => {
    const blob = new Blob([buildCsv(rows)], { type: "text/csv" });
    return URL.createObjectURL(blob);
  }, [rows]);

  if (!stage4) return null;

  if (stageState === "not_applicable") {
    return (
      <section className="stage-view stage-view--na">
        <h2>Step 4 — Disease Targets</h2>
        <p className="hf-muted">Not applicable</p>
      </section>
    );
  }

  const effectivePageSize = pageSize === "all" ? Math.max(1, rows.length) : pageSize;
  const totalPages = Math.max(1, Math.ceil(rows.length / effectivePageSize));
  const currentPage = Math.min(page, totalPages - 1);
  const visibleRows = rows.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  const effectiveCount = stage4.targets.filter((t) => t.tag !== "user-removed").length;
  const entities = stage4.targets.map((t) => ({
    id: t.target_id,
    label: t.canonical_name ?? t.target_id,
    tag: t.tag,
  }));

  const handleAddTargets = useCallback(
    (resolved: ResolvedTarget[]) => {
      const currentIds = new Set((stage4?.targets ?? []).map((t) => t.target_id));
      const already = resolved.filter((r) => currentIds.has(r.target_id));
      const fresh = resolved.filter((r) => !currentIds.has(r.target_id));
      setAlreadyInRun(already);
      if (fresh.length > 0) {
        edit.mutate({ add: fresh.map((r) => r.target_id), remove: [] });
      }
    },
    [stage4, edit],
  );

  return (
    <section className="stage-view stage-view--4">
      <h2>Step 4 — Disease Targets</h2>
      <StageDataSources stage={4} />

      <div className="stage-summary">
        <div className="summary-card" aria-label={`${stage4.count} targets`}>
          <span className="summary-card__value">{stage4.count}</span>
          <span className="summary-card__label">targets</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`min score ${stage4.min_score_applied}`}
        >
          <span className="summary-card__value">{stage4.min_score_applied}</span>
          <span className="summary-card__label">min score</span>
        </div>
      </div>

      {stage4.count === 0 && (
        <p className="hf-muted" role="status">
          No disease targets at this score floor. Lower the min score and Redo, or add targets by
          hand.
        </p>
      )}

      <div className="table-controls">
        <label htmlFor="t4-page-size">Rows per page</label>
        <select
          id="t4-page-size"
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
          download="disease-targets.csv"
          className="hf-btn hf-btn-ghost"
          aria-label="Download CSV"
        >
          Download CSV
        </a>
      </div>

      <div className="table-wrapper">
        <table className="hf-table">
          <thead>
            <tr>
              <th>Gene symbol</th>
              <th>UniProt</th>
              <th>Score</th>
              <th>Association</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr
                key={row.target_id}
                className={row.tag === "user-removed" ? "row--removed" : undefined}
              >
                <td>{row.gene_symbol}</td>
                <td>
                  {row.uniprot_accession ? (
                    row.source_url ? (
                      <a href={row.source_url} target="_blank" rel="noopener noreferrer">
                        {row.uniprot_accession}
                      </a>
                    ) : (
                      row.uniprot_accession
                    )
                  ) : (
                    "—"
                  )}
                </td>
                <td>{row.score == null ? "—" : row.score}</td>
                <td>{row.association_type ?? "—"}</td>
                <td>{tagBadge(row.tag)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

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

      <EditableEntityList
        entities={entities}
        onRemove={(id) => edit.mutate({ add: [], remove: [id] })}
        cap={MAX_TARGETS}
        current={effectiveCount}
        addControl={
          <TargetValidateBox
            label="Add disease targets"
            onResolved={handleAddTargets}
            showAddButton
          />
        }
      />

      {/* Already-in-run note */}
      {alreadyInRun.length > 0 && (
        <p className="hf-muted" role="status">
          {alreadyInRun.length} already in run:{" "}
          {alreadyInRun.map((t) => t.gene_symbol ?? t.uniprot_accession ?? t.target_id).join(", ")}
        </p>
      )}

      {dtParams && (
        <ParamPanel
          params={dtParams}
          meta={DISEASE_TARGETS_PARAMS}
          numericKeys={DISEASE_TARGETS_NUMERIC_PARAMS}
          booleanKeys={[]}
          title="Disease-target parameters"
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {(stage4 as { stale?: boolean }).stale && rerunFrom != null && (
        <StaleNotice analysisId={data.analysis_id} fromStage={rerunFrom} />
      )}
      <ApprovalBar
        stage={4}
        status={data.status}
        currentStage={data.current_stage}
        disabled={stage4.count === 0 || anyStale}
        disabledReason={
          anyStale
            ? "Re-run the out-of-date step before continuing."
            : "No disease targets — lower min score and Redo, or add one to continue."
        }
        onApprove={() => advance.mutate()}
      />

      <footer className="stage-footer hf-muted">
        <p>Disease targets: Open Targets (database snapshot). Human targets only (9606).</p>
      </footer>
    </section>
  );
}
