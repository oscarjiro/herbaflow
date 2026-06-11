/**
 * Stage3View — compound → target identification results.
 *
 * Renders:
 *  - Summary cards: target count, coverage %, and per-source edge counts
 *    (ChEMBL bioactivity / PubChem BioAssay)
 *  - Targets table (one row per target): gene symbol, UniProt accession (linked),
 *    evidence/method(s), # compounds, and an edit tag badge
 *  - Pagination (10 / 20 / 50 / all) and a CSV download keyed on gene symbol +
 *    UniProt accession + method + source_url (NEVER a UUID column)
 *  - Per-compound coverage table (0-coverage rows always visible)
 *  - Target add/remove via EditableEntityList + TargetValidateBox (editStage)
 *  - ParamPanel + Redo (resetFrom) and ApprovalBar
 *  - StpDialog for manual SwissTargetPrediction paste-back
 *
 * State handling (stage_state["3"]):
 *  - "not_applicable" → greyed/disabled note
 *  - "user_provided"  → targets list only (no compounds, no coverage, no STP)
 *  - otherwise (computed) → full view
 */

import { useMemo, useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisRead, ResolvedTarget } from "../../api/types.gen";
import { advanceAnalysis, editStage, resetFrom } from "../../api/sdk.gen";
import { MAX_TARGETS, TARGET_NUMERIC_PARAMS, TARGET_PARAMS } from "../../contract";
import { useStaleState } from "../../hooks/useStaleState";
import { ApprovalBar } from "./ApprovalBar";
import { EditableEntityList } from "./EditableEntityList";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
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
  tag: TargetTag;
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

/** Group edges by target_id, join with the tagged targets list. */
function buildTargetRows(stage3: Stage3Result): TargetRow[] {
  const edgesByTarget = new Map<string, CompoundTargetEdge[]>();
  for (const edge of stage3.compound_targets) {
    const list = edgesByTarget.get(edge.target_id) ?? [];
    list.push(edge);
    edgesByTarget.set(edge.target_id, list);
  }

  return stage3.targets.map((t) => {
    const edges = edgesByTarget.get(t.target_id) ?? [];
    const methods = Array.from(new Set(edges.map((e) => e.prediction_method)));
    const compoundCount = new Set(edges.map((e) => e.compound_id)).size;
    const accEdge = edges.find((e) => e.uniprot_accession);
    return {
      target_id: t.target_id,
      gene_symbol: t.canonical_name ?? t.target_id,
      uniprot_accession: accEdge?.uniprot_accession ?? null,
      source_url: accEdge?.source_url ?? null,
      methods,
      compound_count: compoundCount,
      tag: t.tag,
    };
  });
}

function escapeCsv(v: unknown): string {
  if (v == null) return "";
  const s = String(v);
  if (s.includes(",") || s.includes('"') || s.includes("\n")) {
    return `"${s.replace(/"/g, '""')}"`;
  }
  return s;
}

/**
 * CSV keyed on gene symbol + UniProt accession + method + source_url.
 * NEVER includes a UUID column (hard requirement).
 */
function buildCsv(rows: TargetRow[]): string {
  const header = "gene_symbol,uniprot_accession,prediction_method,source_url";
  const body = rows
    .map((r) =>
      [
        escapeCsv(r.gene_symbol),
        escapeCsv(r.uniprot_accession),
        escapeCsv(r.methods.map(methodLabel).join("; ")),
        escapeCsv(r.source_url),
      ].join(","),
    )
    .join("\n");
  return `${header}\n${body}`;
}

function useCsvDownload(rows: TargetRow[]) {
  return useMemo(() => {
    const csv = buildCsv(rows);
    const blob = new Blob([csv], { type: "text/csv" });
    return URL.createObjectURL(blob);
  }, [rows]);
}

function tagBadge(tag: TargetTag): React.ReactElement | null {
  if (tag === "user-added") {
    return <span className="hf-badge hf-badge--added">user-added</span>;
  }
  if (tag === "user-removed") {
    return <span className="hf-badge hf-badge--removed">user-removed</span>;
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
  });

  const redo = useMutation({
    mutationFn: (changed: Record<string, number | boolean | string>) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 3 },
        body: { parameters: { "3": changed } },
      }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: data.analysis_id, stage: 3 }, body }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);
  const [alreadyInRun, setAlreadyInRun] = useState<ResolvedTarget[]>([]);

  const targetRows = useMemo(() => (stage3 ? buildTargetRows(stage3) : []), [stage3]);
  const csvHref = useCsvDownload(targetRows);

  if (!stage3) return null;

  // not_applicable → greyed note.
  if (stageState === "not_applicable") {
    return (
      <section className="stage-view stage-view--na">
        <h2>Step 3 — Target Identification</h2>
        <p className="hf-muted">Not applicable</p>
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

  // Compound name lookup for the coverage table.
  const passed = stage2?.passed ?? [];
  const nameById = new Map(passed.map((c) => [c.compound_id, c.canonical_name]));

  // Effective target count for cap enforcement (exclude user-removed).
  const effectiveCount = stage3.targets.filter((t) => t.tag !== "user-removed").length;

  const entities = stage3.targets.map((t) => ({
    id: t.target_id,
    label: t.canonical_name ?? t.target_id,
    tag: t.tag,
  }));

  const handleAddTargets = useCallback(
    (resolved: ResolvedTarget[]) => {
      const currentIds = new Set((stage3?.targets ?? []).map((t) => t.target_id));
      const already = resolved.filter((r) => currentIds.has(r.target_id));
      const fresh = resolved.filter((r) => !currentIds.has(r.target_id));
      setAlreadyInRun(already);
      if (fresh.length > 0) {
        edit.mutate({ add: fresh.map((r) => r.target_id), remove: [] });
      }
    },
    [stage3, edit],
  );

  const stpCompounds: StpCompound[] = passed.map((c) => ({
    compound_id: c.compound_id,
    canonical_name: c.canonical_name,
    smiles: c.smiles ?? null,
  }));

  return (
    <section className="stage-view stage-view--3">
      <h2>Step 3 — Target Identification</h2>
      <StageDataSources stage={3} />

      {/* Summary cards */}
      <div className="stage-summary">
        <div className="summary-card" aria-label={`${stage3.count} targets`}>
          <span className="summary-card__value">{stage3.count}</span>
          <span className="summary-card__label">targets</span>
        </div>
        <div className="summary-card" aria-label={`${stage3.coverage_pct}% coverage`}>
          <span className="summary-card__value">{stage3.coverage_pct}%</span>
          <span className="summary-card__label">coverage</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`${sourceCounts.chembl_bioactivity ?? 0} ChEMBL edges`}
        >
          <span className="summary-card__value">{sourceCounts.chembl_bioactivity ?? 0}</span>
          <span className="summary-card__label">ChEMBL</span>
        </div>
        <div
          className="summary-card summary-card--muted"
          aria-label={`${sourceCounts.pubchem_bioassay ?? 0} PubChem BioAssay edges`}
        >
          <span className="summary-card__value">{sourceCounts.pubchem_bioassay ?? 0}</span>
          <span className="summary-card__label">PubChem BioAssay</span>
        </div>
      </div>

      {/* Table controls */}
      <div className="table-controls">
        <label htmlFor="t3-page-size">Rows per page</label>
        <select
          id="t3-page-size"
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
          download="targets.csv"
          className="hf-btn hf-btn-ghost"
          aria-label="Download CSV"
        >
          Download CSV
        </a>
      </div>

      {/* Targets table */}
      <div className="table-wrapper">
        <table className="hf-table">
          <thead>
            <tr>
              <th>Gene symbol</th>
              <th>UniProt</th>
              <th>Evidence</th>
              <th># compounds</th>
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
                <td>{row.methods.length > 0 ? row.methods.map(methodLabel).join(", ") : "—"}</td>
                <td>{row.compound_count}</td>
                <td>{tagBadge(row.tag)}</td>
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

      {/* Per-compound coverage — skipped for user_provided (no compounds) */}
      {!isUserProvided && (
        <div className="coverage-table">
          <h3>Per-compound coverage</h3>
          <table className="hf-table">
            <thead>
              <tr>
                <th>Compound</th>
                <th>Targets</th>
              </tr>
            </thead>
            <tbody>
              {Object.entries(stage3.per_compound).map(([compoundId, info]) => (
                <tr
                  key={compoundId}
                  className={info.coverage === 0 ? "row--zero-coverage" : undefined}
                >
                  <td>{nameById.get(compoundId) ?? compoundId}</td>
                  <td>{info.coverage}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {/* Target add / remove */}
      <EditableEntityList
        entities={entities}
        onRemove={(id) => edit.mutate({ add: [], remove: [id] })}
        cap={MAX_TARGETS}
        current={effectiveCount}
        addControl={
          <TargetValidateBox label="Add targets" onResolved={handleAddTargets} showAddButton />
        }
      />

      {/* Already-in-run note */}
      {alreadyInRun.length > 0 && (
        <p className="hf-muted" role="status">
          {alreadyInRun.length} already in run:{" "}
          {alreadyInRun.map((t) => t.gene_symbol ?? t.uniprot_accession ?? t.target_id).join(", ")}
        </p>
      )}

      {/* Param panel */}
      {targetParams && (
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
            ? "Re-run the out-of-date step before continuing."
            : "No targets — adjust parameters or add one to continue."
        }
        onApprove={() => advance.mutate()}
      />

      {/* Footer */}
      <footer className="stage-footer hf-muted">
        <p>Targets: ChEMBL + PubChem BioAssay. Human targets only (9606).</p>
      </footer>
    </section>
  );
}
