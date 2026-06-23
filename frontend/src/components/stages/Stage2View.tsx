/**
 * Stage2View — ADME screening results.
 *
 * Renders:
 *  - Stage entity context + summary count cards
 *  - A combined passed + filtered DataTable with Stage 2 outcomes, source links,
 *    and reasons for filtered rows
 *  - CsvDownloadButton (same header + rows as before)
 *  - Collapsible ParamPanel wired to resetFrom
 *  - "Tools & data sources" footer
 *
 * The stage header and ApprovalBar are owned by the StageView shell.
 * Defensive rendering: greyed out when state === "not_applicable".
 */

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead } from "../../api/types.gen";
import { resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import { ADME_PARAMS } from "../../contract";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataTable } from "@/components/ui/DataTable";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StageEntityContext } from "./StageEntityContext";

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
  qed_score: number | null;
  np_likeness_score: number | null;
  num_ro5_violations?: number | null;
  lipinski_violations: number | null;
  lipinski_pass: boolean | null;
  veber_pass: boolean | null;
  rule_evaluated: boolean | null;
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

type DisplayRow = CompoundRow & { _kind: "passed" | "filtered" };

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function fmt(n: number | null, decimals = 2): string {
  if (n == null) return "—";
  return n.toFixed(decimals);
}

function fmtOutcome(
  passed: boolean | null | undefined,
  evaluated: boolean | null | undefined,
): string {
  if (!evaluated || passed == null) return "—";
  return passed ? "Pass" : "Fail";
}

function RowBadges({ row }: { row: CompoundRow }) {
  const items: React.ReactElement[] = [];
  if (row.badges?.includes("np_bypass")) {
    items.push(
      <Badge key="np" variant="outline" className="text-[10px]">
        NP-bypass
      </Badge>,
    );
  }
  if (row.badges?.includes("unscreened")) {
    items.push(
      <Badge key="unscreened" variant="outline" className="text-muted-foreground text-[10px]">
        unscreened
      </Badge>,
    );
  }
  if (row.badges?.includes("could_not_screen")) {
    items.push(
      <Badge key="cns" variant="outline" className="text-muted-foreground text-[10px]">
        could-not-screen
      </Badge>,
    );
  }
  return <span className="flex flex-wrap gap-1">{items}</span>;
}

const CSV_COLS: (keyof CompoundRow)[] = [
  "inchikey",
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
  "lipinski_violations",
  "lipinski_pass",
  "veber_pass",
  "rule_evaluated",
  "is_pains_positive",
  "source_url",
  "reason",
];

const CSV_HEADER = CSV_COLS.join(",");

function buildCsvRows(rows: DisplayRow[]): unknown[][] {
  return rows.map((r) => CSV_COLS.map((c) => r[c] ?? null));
}

// ---------------------------------------------------------------------------
// Column definitions for DataTable
// ---------------------------------------------------------------------------

const COLUMNS: ColumnDef<DisplayRow>[] = [
  {
    id: "name",
    header: "Name",
    cell: ({ row }) => {
      const r = row.original;
      return (
        <span className="flex flex-col gap-0.5">
          {r.source_url && (
            <a
              href={r.source_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-[color:var(--hf-accent)] underline underline-offset-2"
            >
              PubChem
            </a>
          )}
          <span>{r.canonical_name ?? r.inchikey ?? r.compound_id}</span>
        </span>
      );
    },
  },
  {
    id: "status",
    header: "Status",
    cell: ({ row }) => {
      const kind = row.original._kind;
      return (
        <Badge variant={kind === "passed" ? "default" : "destructive"} className="text-[10px]">
          {kind}
        </Badge>
      );
    },
  },
  {
    id: "badges",
    header: "Badges",
    cell: ({ row }) => <RowBadges row={row.original} />,
  },
  {
    accessorKey: "descriptor_source",
    header: "Descriptor source",
  },
  {
    id: "mw",
    header: "MW",
    cell: ({ row }) => fmt(row.original.molecular_weight, 1),
  },
  {
    id: "logp",
    header: "logP",
    cell: ({ row }) => fmt(row.original.logp),
  },
  {
    id: "hbd",
    header: "HBD",
    cell: ({ row }) => row.original.hbond_donors ?? "—",
  },
  {
    id: "hba",
    header: "HBA",
    cell: ({ row }) => row.original.hbond_acceptors ?? "—",
  },
  {
    id: "tpsa",
    header: "TPSA",
    cell: ({ row }) => fmt(row.original.tpsa, 1),
  },
  {
    id: "rotb",
    header: "RotB",
    cell: ({ row }) => row.original.rotatable_bonds ?? "—",
  },
  {
    id: "qed",
    header: "QED",
    cell: ({ row }) => fmt(row.original.qed_score),
  },
  {
    id: "np",
    header: "NP score",
    cell: ({ row }) => fmt(row.original.np_likeness_score),
  },
  {
    id: "lipinski",
    header: "Lipinski",
    cell: ({ row }) => fmtOutcome(row.original.lipinski_pass, row.original.rule_evaluated),
  },
  {
    id: "veber",
    header: "Veber",
    cell: ({ row }) => fmtOutcome(row.original.veber_pass, row.original.rule_evaluated),
  },
  {
    id: "pains",
    header: "PAINS",
    cell: ({ row }) =>
      row.original.rule_evaluated
        ? row.original.is_pains_positive
          ? "Positive"
          : "Negative"
        : "—",
  },
  {
    id: "reason",
    header: "Reason",
    cell: ({ row }) => row.original.reason ?? "",
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

  const qc = useQueryClient();

  const redo = useMutation({
    mutationFn: (changed: Record<string, number | boolean | string>) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 2 },
        body: { parameters: { "2": changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo("Re-running from step 2");
    },
    onError: (error) => notifyError(error as Problem),
  });

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
    return (
      <section className="stage-view stage-view--na" aria-disabled>
        <h2>Step 2: ADME Screening</h2>
        <p className={cn("text-sm", "[color:var(--hf-fg-3)]")}>Not applicable for this run.</p>
      </section>
    );
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
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${passedCount} passed`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{passedCount}</span>
          <span className="text-muted-foreground text-xs">passed</span>
        </div>
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${filteredCount} filtered`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{filteredCount}</span>
          <span className="text-muted-foreground text-xs">filtered</span>
        </div>
        {unscreenedCount > 0 && (
          <div
            className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
            aria-label={`${unscreenedCount} unscreened`}
          >
            <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
              {unscreenedCount}
            </span>
            <span className="text-muted-foreground text-xs">unscreened</span>
          </div>
        )}
      </div>

      {/* Table + controls */}
      {isUserProvided && (
        <div>
          <Badge variant="secondary">Provided by you</Badge>
        </div>
      )}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <CsvDownloadButton
              header={CSV_HEADER}
              rows={csvRows}
              filename="adme-results.csv"
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
          disabled={redo.isPending}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {/* Footer */}
      <p className="text-muted-foreground text-sm">
        Filters: Lipinski RO5, Veber (TPSA + rotatable bonds), Ertl NP-likeness, Baell &amp;
        Holloway PAINS.
      </p>
    </section>
  );
}
