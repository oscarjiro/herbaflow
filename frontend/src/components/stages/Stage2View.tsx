/**
 * Stage2View — ADME screening results.
 *
 * Renders:
 *  - Summary count cards (passed / filtered / unscreened)
 *  - A combined passed + filtered table with badges, QED score, descriptor
 *    source, source_url links, and reasons for filtered rows
 *  - Pagination controls (10 / 20 / 50 / all)
 *  - Client-side CSV download (no external library)
 *  - Collapsible ParamPanel wired to resetFrom
 *  - ApprovalBar (approve → advance)
 *  - "Tools & data sources" footer
 *
 * Defensive rendering: greyed out when state === "not_applicable".
 */

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { AnalysisRead } from "../../api/types.gen";
import { advanceAnalysis, resetFrom } from "../../api/sdk.gen";
import { ADME_PARAMS } from "../../contract";
import { ApprovalBar } from "./ApprovalBar";
import { ParamPanel } from "./ParamPanel";

// ---------------------------------------------------------------------------
// Local types for the Stage 2 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type CompoundRow = {
  compound_id: string;
  canonical_name: string | null;
  descriptor_source: "rdkit" | "etl" | string;
  molecular_weight: number | null;
  logp: number | null;
  hbond_donors: number | null;
  hbond_acceptors: number | null;
  tpsa: number | null;
  rotatable_bonds: number | null;
  qed_score: number | null;
  np_likeness_score: number | null;
  num_ro5_violations: number | null;
  is_pains_positive: boolean;
  source_url: string | null;
  badges?: string[];
  reason?: string;
};

type Stage2Result = {
  count: number;
  state: string;
  passed: CompoundRow[];
  filtered: CompoundRow[];
  annotations: {
    pains: string[];
    np_bypass: string[];
    unscreened: string[];
    could_not_screen: string[];
  };
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const PAGE_SIZES = [10, 20, 50] as const;

function fmt(n: number | null, decimals = 2): string {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

function BadgePill({ label, variant }: { label: string; variant: string }) {
  return (
    <span className={`badge badge--${variant}`} aria-label={label}>
      {label}
    </span>
  );
}

function rowBadges(row: CompoundRow) {
  const badges: React.ReactElement[] = [];
  if (row.badges?.includes("pains") || row.is_pains_positive) {
    badges.push(<BadgePill key="pains" label="PAINS" variant="warning" />);
  }
  if (row.badges?.includes("np_bypass")) {
    badges.push(<BadgePill key="np" label="NP-bypass" variant="info" />);
  }
  if (row.badges?.includes("unscreened")) {
    badges.push(<BadgePill key="unscreened" label="unscreened" variant="muted" />);
  }
  if (row.badges?.includes("could_not_screen")) {
    badges.push(<BadgePill key="cns" label="could-not-screen" variant="muted" />);
  }
  return badges;
}

// Build a CSV string from a flat array of objects
function buildCsv(rows: CompoundRow[]): string {
  const cols: (keyof CompoundRow)[] = [
    "compound_id",
    "canonical_name",
    "descriptor_source",
    "molecular_weight",
    "logp",
    "hbond_donors",
    "hbond_acceptors",
    "tpsa",
    "rotatable_bonds",
    "qed_score",
    "np_likeness_score",
    "num_ro5_violations",
    "is_pains_positive",
    "source_url",
    "reason",
  ];
  const escape = (v: unknown) => {
    if (v == null) return "";
    const s = String(v);
    if (s.includes(",") || s.includes('"') || s.includes("\n")) {
      return `"${s.replace(/"/g, '""')}"`;
    }
    return s;
  };
  const header = cols.join(",");
  const body = rows.map((r) => cols.map((c) => escape(r[c])).join(",")).join("\n");
  return `${header}\n${body}`;
}

function useCsvDownload(rows: CompoundRow[]) {
  const href = useMemo(() => {
    const csv = buildCsv(rows);
    const blob = new Blob([csv], { type: "text/csv" });
    return URL.createObjectURL(blob);
  }, [rows]);
  return href;
}

// ---------------------------------------------------------------------------
// Stage2View
// ---------------------------------------------------------------------------

export function Stage2View({ data }: { data: AnalysisRead }) {
  const stage2 = data.stage_results?.["2"] as Stage2Result | undefined;
  const admeParams = (data.parameters as Record<string, unknown> | undefined)?.adme as
    | Record<string, number | boolean>
    | undefined;

  const qc = useQueryClient();

  const advance = useMutation({
    mutationFn: () => advanceAnalysis({ path: { analysis_id: data.analysis_id } }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const redo = useMutation({
    mutationFn: (changed: Record<string, number | boolean>) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 2 },
        body: { parameters: { "2": changed } },
      }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  if (!stage2) return null;

  const isNA = stage2.state === "not_applicable";
  if (isNA) {
    return (
      <section className="stage-view stage-view--na">
        <h2>Step 2 — ADME Screening</h2>
        <p className="hf-muted">Not applicable</p>
      </section>
    );
  }

  const allRows: (CompoundRow & { _kind: "passed" | "filtered" })[] = [
    ...stage2.passed.map((r) => ({ ...r, _kind: "passed" as const })),
    ...stage2.filtered.map((r) => ({ ...r, _kind: "filtered" as const })),
  ];

  const effectivePageSize = pageSize === "all" ? allRows.length : pageSize;
  const totalPages = Math.ceil(allRows.length / effectivePageSize);
  const currentPage = Math.min(page, Math.max(0, totalPages - 1));
  const visibleRows = allRows.slice(
    currentPage * effectivePageSize,
    (currentPage + 1) * effectivePageSize,
  );

  const csvHref = useCsvDownload(allRows);

  const passedCount = stage2.passed.length;
  const filteredCount = stage2.filtered.length;
  const unscreenedCount = stage2.annotations.unscreened.length;

  return (
    <section className="stage-view stage-view--2">
      <h2>Step 2 — ADME Screening</h2>

      {/* Summary cards */}
      <div className="stage-summary">
        <div className="summary-card" aria-label={`${passedCount} passed`}>
          <span className="summary-card__value">{passedCount}</span>
          <span className="summary-card__label">passed</span>
        </div>
        <div
          className="summary-card summary-card--filtered"
          aria-label={`${filteredCount} filtered`}
        >
          <span className="summary-card__value">{filteredCount}</span>
          <span className="summary-card__label">filtered</span>
        </div>
        {unscreenedCount > 0 && (
          <div
            className="summary-card summary-card--muted"
            aria-label={`${unscreenedCount} unscreened`}
          >
            <span className="summary-card__value">{unscreenedCount}</span>
            <span className="summary-card__label">unscreened</span>
          </div>
        )}
      </div>

      {/* Table controls */}
      <div className="table-controls">
        <label htmlFor="page-size">Rows per page</label>
        <select
          id="page-size"
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
          download="adme-results.csv"
          className="hf-btn hf-btn-ghost"
          aria-label="Download CSV"
        >
          Download CSV
        </a>
      </div>

      {/* Compound table */}
      <div className="table-wrapper">
        <table className="hf-table">
          <thead>
            <tr>
              <th>Name</th>
              <th>Status</th>
              <th>Badges</th>
              <th>MW</th>
              <th>logP</th>
              <th>HBD</th>
              <th>HBA</th>
              <th>TPSA</th>
              <th>RotB</th>
              <th>QED</th>
              <th>NP score</th>
              <th>RO5 viol.</th>
              <th>Source</th>
              <th>Reason</th>
            </tr>
          </thead>
          <tbody>
            {visibleRows.map((row) => (
              <tr
                key={row.compound_id}
                className={row._kind === "filtered" ? "row--filtered" : undefined}
              >
                <td>
                  {row.source_url ? (
                    <a href={row.source_url} target="_blank" rel="noopener noreferrer">
                      PubChem
                    </a>
                  ) : null}
                  {row.canonical_name ?? row.compound_id}
                </td>
                <td>{row._kind}</td>
                <td>{rowBadges(row)}</td>
                <td>{fmt(row.molecular_weight, 1)}</td>
                <td>{fmt(row.logp)}</td>
                <td>{row.hbond_donors ?? "—"}</td>
                <td>{row.hbond_acceptors ?? "—"}</td>
                <td>{fmt(row.tpsa, 1)}</td>
                <td>{row.rotatable_bonds ?? "—"}</td>
                <td>{fmt(row.qed_score)}</td>
                <td>{fmt(row.np_likeness_score)}</td>
                <td>{row.num_ro5_violations ?? "—"}</td>
                <td>{row.descriptor_source}</td>
                <td>{row.reason ?? ""}</td>
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

      {/* Param panel */}
      {admeParams && (
        <ParamPanel
          params={admeParams}
          meta={ADME_PARAMS}
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {/* Approval */}
      <ApprovalBar
        stage={2}
        status={data.status}
        currentStage={data.current_stage}
        disabled={stage2.count === 0}
        disabledReason="No compounds passed ADME — adjust parameters and Redo to continue."
        onApprove={() => advance.mutate()}
      />

      {/* Footer */}
      <footer className="stage-footer hf-muted">
        <p>
          Descriptors computed with <strong>RDKit</strong>. Filters: Lipinski RO5, Veber (TPSA +
          rotatable bonds), Ertl NP-likeness, Baell &amp; Holloway PAINS.
        </p>
      </footer>
    </section>
  );
}
