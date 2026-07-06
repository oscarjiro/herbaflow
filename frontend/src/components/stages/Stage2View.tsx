/**
 * Stage2View — ADME screening results.
 *
 * Renders:
 *  - Stage entity context + summary count cards
 *  - A combined passed + filtered DataTable with Stage 2 outcomes and reasons for filtered rows
 *  - CsvDownloadButton (same header + rows as before)
 *  - Collapsible ParamPanel wired to resetFrom
 *  - "Tools & data sources" footer
 *
 * The stage header and ApprovalBar are owned by the StageView shell.
 * Defensive rendering: greyed out when state === "not_applicable".
 */

import { useMemo } from "react";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead } from "../../api/types.gen";
import { useParamRedo } from "@/hooks/useParamRedo";
import { ADME_PARAMS } from "../../contract";
import { formatSig, formatCount } from "../../lib/format";
import { METRIC_INFO } from "../../lib/metricInfo";
import { StageNotApplicable } from "./StageNotApplicable";
import { ProvidedByYouBadge } from "./ProvidedByYouBadge";
import { Badge } from "@/components/ui/badge";
import { BoolMark } from "@/components/ui/BoolMark";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataTable } from "@/components/ui/DataTable";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { ParamPanel } from "./ParamPanel";
import { isRunBusy } from "@/lib/runStatus";
import { StageDataSources } from "./StageDataSources";
import { StageEntityContext } from "./StageEntityContext";
import { StageSummaryCard } from "./StageSummaryCard";

// ---------------------------------------------------------------------------
// Local types for the Stage 2 result shape (narrowed from unknown)
// ---------------------------------------------------------------------------

type CompoundRow = {
  compound_id: string;
  inchikey: string | null;
  canonical_name: string | null;
  descriptor_source: "rdkit" | "etl" | string;
  molecular_weight: number | null;
  logp: number | null;
  hbond_donors: number | null;
  hbond_acceptors: number | null;
  tpsa: number | null;
  rotatable_bonds: number | null;
  np_likeness_score: number | null;
  num_ro5_violations?: number | null;
  lipinski_violations: number | null;
  lipinski_pass: boolean | null;
  veber_pass: boolean | null;
  rule_evaluated: boolean | null;
  is_pains_positive: boolean;
  pains_evaluated?: boolean;
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

type DisplayRow = CompoundRow & { _kind: "passed" | "filtered" };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Derive a boolean NP-bypass value from the row's badges array. */
function npBypass(row: CompoundRow): boolean | null {
  if (!row.rule_evaluated) return null;
  return row.badges?.includes("np_bypass") ?? false;
}

// ---------------------------------------------------------------------------
// CSV builder
// ---------------------------------------------------------------------------

const CSV_HEADER =
  "name,status,lipinski_pass,veber_pass,np_bypass,mw,logp,hbd,hba,tpsa,rotb,np_score,pains,source_url";

function buildCsvRows(rows: DisplayRow[]): unknown[][] {
  return rows.map((r) => [
    r.canonical_name ?? r.inchikey ?? r.compound_id,
    r._kind,
    r.lipinski_pass ?? null,
    r.veber_pass ?? null,
    npBypass(r),
    r.molecular_weight ?? null,
    r.logp ?? null,
    r.hbond_donors ?? null,
    r.hbond_acceptors ?? null,
    r.tpsa ?? null,
    r.rotatable_bonds ?? null,
    r.np_likeness_score ?? null,
    r.pains_evaluated ? r.is_pains_positive : null,
    r.source_url ?? null,
  ]);
}

// ---------------------------------------------------------------------------
// Column definitions for DataTable
// ---------------------------------------------------------------------------

const COLUMNS: ColumnDef<DisplayRow>[] = [
  {
    id: "name",
    accessorFn: (row) => row.canonical_name ?? row.inchikey ?? row.compound_id,
    header: "Name",
    cell: ({ row }) => {
      const r = row.original;
      const label = r.canonical_name ?? r.inchikey ?? r.compound_id;
      if (!r.source_url) return <span>{label}</span>;
      return <ExternalLink href={r.source_url}>{label}</ExternalLink>;
    },
  },
  {
    id: "status",
    header: "Status",
    meta: { info: METRIC_INFO.s2.status },
    cell: ({ row }) => {
      const r = row.original;
      const passed = r._kind === "passed";
      const npBypassed = passed && (r.badges?.includes("np_bypass") ?? false);
      return (
        <span className="inline-flex items-center gap-1.5">
          <Badge variant={passed ? "default" : "destructive"} className="text-[10px]">
            {passed ? "Passed" : "Filtered"}
          </Badge>
          {npBypassed && (
            <Badge
              variant="secondary"
              className="text-[10px]"
              title="Passed via the natural-product exception; drug-likeness rules were not applied."
            >
              NP exception
            </Badge>
          )}
        </span>
      );
    },
  },
  {
    id: "lipinski",
    header: "Lipinski",
    meta: { info: METRIC_INFO.s2.lipinski },
    cell: ({ row }) => {
      const r = row.original;
      if (!r.rule_evaluated) return <BoolMark value={null} />;
      return <BoolMark value={r.lipinski_pass} />;
    },
  },
  {
    id: "veber",
    header: "Veber",
    meta: { info: METRIC_INFO.s2.veber },
    cell: ({ row }) => {
      const r = row.original;
      if (!r.rule_evaluated) return <BoolMark value={null} />;
      return <BoolMark value={r.veber_pass} />;
    },
  },
  {
    id: "np_bypass",
    header: "NP-bypass",
    meta: { info: METRIC_INFO.s2.npBypass },
    cell: ({ row }) => <BoolMark value={npBypass(row.original)} />,
  },
  {
    id: "mw",
    header: "MW",
    meta: { className: "num", info: METRIC_INFO.s2.mw },
    cell: ({ row }) => formatSig(row.original.molecular_weight),
  },
  {
    id: "logp",
    header: "logP",
    meta: { className: "num", info: METRIC_INFO.s2.logp },
    cell: ({ row }) => formatSig(row.original.logp),
  },
  {
    id: "hbd",
    header: "HBD",
    meta: { className: "num", info: METRIC_INFO.s2.hbd },
    cell: ({ row }) => formatCount(row.original.hbond_donors),
  },
  {
    id: "hba",
    header: "HBA",
    meta: { className: "num", info: METRIC_INFO.s2.hba },
    cell: ({ row }) => formatCount(row.original.hbond_acceptors),
  },
  {
    id: "tpsa",
    header: "TPSA",
    meta: { className: "num", info: METRIC_INFO.s2.tpsa },
    cell: ({ row }) => formatSig(row.original.tpsa),
  },
  {
    id: "rotb",
    header: "RotB",
    meta: { className: "num", info: METRIC_INFO.s2.rotb },
    cell: ({ row }) => formatCount(row.original.rotatable_bonds),
  },
  {
    id: "np_score",
    header: "NP-score",
    meta: { className: "num", info: METRIC_INFO.s2.npScore },
    cell: ({ row }) => formatSig(row.original.np_likeness_score),
  },
  {
    id: "pains",
    header: "PAINS",
    meta: { info: METRIC_INFO.s2.pains },
    cell: ({ row }) => {
      const r = row.original;
      if (!r.pains_evaluated) return <BoolMark value={null} />;
      return <BoolMark value={!r.is_pains_positive} />;
    },
  },
];

// ---------------------------------------------------------------------------
// Stage2View
// ---------------------------------------------------------------------------

export function Stage2View({ data }: { data: AnalysisRead }) {
  const stage2 = data.stage_results?.["2"] as Stage2Result | undefined;
  const admeParams = (data.parameters as Record<string, unknown> | undefined)?.adme as
    | Record<string, number | boolean>
    | undefined;

  const redo = useParamRedo<Record<string, number | boolean | string>>(data.analysis_id, 2);

  // Read the single canonical entry-mode source (stage_state), like Stages 1/3/4.
  // S2 is always computed, so stage_state["2"] is normally "computed" — but never key UI off
  // the presentational stage2.state (it flips to user_provided on edits).
  const stageState = (data as { stage_state?: Record<string, string> }).stage_state?.["2"];
  const isNA = stageState === "not_applicable";
  const isUserProvided = stageState === "user_provided";

  // All hooks must precede any early return (Rules of Hooks).
  const allRows: DisplayRow[] = useMemo(
    () => [
      ...(stage2?.passed ?? []).map((r) => ({ ...r, _kind: "passed" as const })),
      ...(stage2?.filtered ?? []).map((r) => ({ ...r, _kind: "filtered" as const })),
    ],
    [stage2],
  );

  const csvRows = useMemo(() => buildCsvRows(allRows), [allRows]);

  // Early returns after all hooks.
  if (!stage2) return null;

  if (isNA) {
    return <StageNotApplicable stage={2} />;
  }

  const passedCount = stage2.passed.length;
  const filteredCount = stage2.filtered.length;
  const unscreenedCount = stage2.annotations.unscreened.length;

  return (
    <section className="flex flex-col gap-6">
      <StageEntityContext data={data} side="plant" />

      <StageDataSources stage={2} userProvided={isUserProvided} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <StageSummaryCard
          value={formatCount(passedCount)}
          label="passed"
          ariaLabel={`${passedCount} passed`}
          info={METRIC_INFO.s2.passed}
        />
        <StageSummaryCard
          value={formatCount(filteredCount)}
          label="filtered"
          ariaLabel={`${filteredCount} filtered`}
          info={METRIC_INFO.s2.filtered}
        />
        {unscreenedCount > 0 && (
          <StageSummaryCard
            value={formatCount(unscreenedCount)}
            label="unscreened"
            ariaLabel={`${unscreenedCount} unscreened`}
            muted
            info={METRIC_INFO.s2.unscreened}
          />
        )}
      </div>

      {/* Table + controls */}
      <ProvidedByYouBadge show={isUserProvided} />
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <CsvDownloadButton
              header={CSV_HEADER}
              rows={csvRows}
              filename="adme.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="px-0">
          <DataTable columns={COLUMNS} data={allRows} />
        </CardContent>
      </Card>

      {/* Param panel */}
      {admeParams && (
        <ParamPanel
          params={admeParams}
          meta={ADME_PARAMS}
          disabled={redo.isPending || isRunBusy(data.status)}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {/* Footer */}
      <p className="text-muted-foreground text-sm">
        Filters: Lipinski RO5 and Veber (TPSA plus rotatable bonds). Natural-product-like compounds
        can bypass these filters as an exception.
      </p>
    </section>
  );
}
