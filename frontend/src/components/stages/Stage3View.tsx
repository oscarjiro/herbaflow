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
 *  - Target remove via an in-table delete column; add via a standalone EntityAddControl +
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
import { useCsvBlobUrl } from "../../lib/csv";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisRead, ResolvedTarget } from "../../api/types.gen";
import { advanceAnalysis, editStage, resetFrom } from "../../api/sdk.gen";
import { MAX_TARGETS, TARGET_NUMERIC_PARAMS, TARGET_PARAMS } from "../../contract";
import { atMinEntities, isUserRemoved } from "../../lib/entities";
import { formatSig } from "../../lib/format";
import { useAddWithDedup } from "../../hooks/useAddWithDedup";
import { useStaleState } from "../../hooks/useStaleState";
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
      return {
        target_id: t.target_id,
        gene_symbol: t.canonical_name ?? t.target_id,
        uniprot_accession: accEdge?.uniprot_accession ?? null,
        source_url: accEdge?.source_url ?? null,
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
  const csvHref = useCsvBlobUrl(S3_CSV_HEADER, buildS3CsvRows(targetRows));

  if (!stage3) return null;

  // not_applicable → greyed note.
  if (stageState === "not_applicable") {
    return (
      <section className="stage-view stage-view--na" aria-disabled>
        <h2>Step 3 — Target Identification</h2>
        <p className="hf-muted">Not applicable for this run.</p>
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

  return (
    <section className="stage-view stage-view--3">
      <h2>
        Step 3 — Target Identification
        {isUserProvided && <span className="hf-badge hf-badge--provided"> Provided by you</span>}
      </h2>
      <StageDataSources stage={3} />
      <StageEntityContext data={data} side="plant" />

      {/* Summary cards */}
      <div className="stage-summary">
        <div className="summary-card" aria-label={`${stage3.count} targets`}>
          <span className="summary-card__value">{stage3.count}</span>
          <span className="summary-card__label">targets</span>
        </div>
        {!isUserProvided && (
          <>
            <div
              className="summary-card"
              aria-label={`${formatSig(stage3.coverage_pct)}% coverage`}
            >
              <span className="summary-card__value">{formatSig(stage3.coverage_pct)}%</span>
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
          </>
        )}
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
                <td>
                  <button
                    className="hf-btn hf-btn-icon"
                    aria-label={`Remove ${row.gene_symbol}`}
                    onClick={() => edit.mutate({ add: [], remove: [row.target_id] })}
                    disabled={atMinEntities(effectiveCount)}
                    title={
                      atMinEntities(effectiveCount)
                        ? "A stage must keep at least one entry."
                        : undefined
                    }
                  >
                    ✕
                  </button>
                </td>
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
