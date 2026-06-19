/**
 * Stage4View — disease → target collection results (DB read of the seeded Open Targets snapshot).
 *
 * Renders:
 *  - Editorial header (Eyebrow + serif h2) with summary count cards: target count + the applied
 *    min_score (min_score hidden for user_provided)
 *  - Disease-targets DataTable (one row per target): gene symbol, UniProt accession (linked), Open
 *    Targets score (display-rounded), edit tag badge, in-table delete; pagination (10/20/50/all);
 *    CSV keyed on gene_symbol + uniprot_accession + opentargets_score + source_url (NEVER a UUID; the
 *    near-constant association_type is kept on the data type but no longer surfaced or exported)
 *  - User-removed rows are hidden from the table AND the CSV (data still persists)
 *  - Target remove via the in-table delete column; add via a standalone EntityAddControl +
 *    TargetValidateBox (editStage stage 4)
 *  - ParamPanel (min_score) + Redo (resetFrom stage 4) and ApprovalBar — both the ParamPanel and
 *    the min-score card are hidden for user_provided; at count 0 the ApprovalBar is disabled with a
 *    reason (blocking-stop); recover via Redo or a manual add
 *  - Footer: "Disease targets: Open Targets (database snapshot). Human targets only (9606)."
 *
 * State (stage_state["4"]):
 *  - "not_applicable" → greyed note
 *  - "user_provided"  → manual disease-targets (no score emphasis)
 *  - otherwise (computed) → full view
 * Stage 4 emits ONE enriched `targets` list — each row carries gene_symbol / uniprot_accession /
 * opentargets_score / association_type / source_url (no separate `disease_targets` view list; B-DUP-2/L-11).
 * A manually-added target has no disease edge, so its opentargets_score column renders "—" (symmetric with
 * Stage 3 user-added targets).
 */

import { useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead, ResolvedTarget } from "../../api/types.gen";
import { advanceAnalysis, editStage, resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import {
  DISEASE_TARGETS_NUMERIC_PARAMS,
  DISEASE_TARGETS_PARAMS,
  MAX_TARGETS,
} from "../../contract";
import { atMinEntities, isUserRemoved } from "../../lib/entities";
import { formatSig } from "../../lib/format";
import { useAddWithDedup } from "../../hooks/useAddWithDedup";
import { useStaleState } from "../../hooks/useStaleState";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataTable } from "@/components/ui/DataTable";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { Eyebrow } from "@/components/ui/editorial";
import { AlreadyInRunNote } from "./AlreadyInRunNote";
import { ApprovalBar } from "./ApprovalBar";
import { EntityAddControl } from "./EntityAddControl";
import { ParamPanel } from "./ParamPanel";
import { StageDataSources } from "./StageDataSources";
import { StageEntityContext } from "./StageEntityContext";
import { StaleNotice } from "./StaleNotice";
import { TargetValidateBox } from "../TargetValidateBox";

type TargetTag = "computed" | "user-added" | "user-removed" | string;

// One enriched edit-layer targets list — each row carries the Open Targets association fields
// (no separate disease_targets view list; B-DUP-2/L-11). A user-added target has no opentargets_score.
type TargetEntry = {
  target_id: string;
  canonical_name: string | null;
  gene_symbol?: string | null;
  uniprot_accession?: string | null;
  opentargets_score?: number | null;
  association_type?: string | null;
  source_url?: string | null;
  tag: TargetTag;
};

type Stage4Result = {
  targets: TargetEntry[];
  count: number;
  min_score_applied: number;
  state: string;
};

type Row = {
  target_id: string;
  gene_symbol: string;
  uniprot_accession: string | null;
  opentargets_score: number | null;
  source_url: string | null;
  tag: TargetTag;
};

const PAGE_SIZES = [10, 20, 50] as const;

function buildRows(stage4: Stage4Result): Row[] {
  return stage4.targets
    .filter((t) => !isUserRemoved(t.tag)) // hidden; data still persists
    .map((t) => ({
      target_id: t.target_id,
      gene_symbol: t.canonical_name ?? t.gene_symbol ?? t.target_id,
      uniprot_accession: t.uniprot_accession ?? null,
      opentargets_score: t.opentargets_score ?? null,
      source_url: t.source_url ?? null,
      tag: t.tag,
    }));
}

// CSV keyed on gene symbol + UniProt accession + opentargets_score + source_url (NEVER a UUID, and
// the near-constant association_type is no longer surfaced). Values stay RAW (no display rounding).
const S4_CSV_HEADER = "gene_symbol,uniprot_accession,opentargets_score,source_url";

function buildS4CsvRows(rows: Row[]): unknown[][] {
  return rows.map((r) => [r.gene_symbol, r.uniprot_accession, r.opentargets_score, r.source_url]);
}

function tagBadge(tag: TargetTag): React.ReactElement | null {
  if (tag === "user-added") {
    return (
      <Badge variant="secondary" className="text-[10px]">
        user-added
      </Badge>
    );
  }
  if (tag === "user-removed") {
    return (
      <Badge variant="destructive" className="text-[10px]">
        user-removed
      </Badge>
    );
  }
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
    onError: (error) => notifyError(error as Problem),
  });
  const redo = useMutation({
    mutationFn: (changed: Record<string, number | boolean | string>) =>
      resetFrom({
        path: { analysis_id: data.analysis_id, stage: 4 },
        body: { parameters: { "4": changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo("Re-running from step 4");
    },
    onError: (error) => notifyError(error as Problem),
  });
  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: data.analysis_id, stage: 4 }, body }),
    onSuccess: () => qc.invalidateQueries(),
    onError: (error) => notifyError(error as Problem),
  });

  const [pageSize, setPageSize] = useState<number | "all">(10);
  const [page, setPage] = useState(0);

  const currentTargetIds = new Set((stage4?.targets ?? []).map((t) => t.target_id));
  const { alreadyInRun, handleAdd: handleAddTargets } = useAddWithDedup<ResolvedTarget>({
    currentIds: currentTargetIds,
    getId: (r) => r.target_id,
    onAddIds: (ids) => edit.mutate({ add: ids, remove: [] }),
  });

  const rows = useMemo(() => (stage4 ? buildRows(stage4) : []), [stage4]);
  const csvRows = useMemo(() => buildS4CsvRows(rows), [rows]);

  if (!stage4) return null;

  if (stageState === "not_applicable") {
    return (
      <section className="stage-view stage-view--na" aria-disabled>
        <h2>Step 4: Disease Targets</h2>
        <p className={cn("text-sm", "[color:var(--hf-fg-3)]")}>Not applicable for this run.</p>
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

  const isUserProvided = stageState === "user_provided";

  // Per-target column definitions — SAME columns + order as the prior table, plus the delete action.
  const columns: ColumnDef<Row>[] = [
    {
      id: "gene_symbol",
      header: "Gene symbol",
      cell: ({ row }) => row.original.gene_symbol,
    },
    {
      id: "uniprot",
      header: "UniProt",
      cell: ({ row }) => {
        const r = row.original;
        if (!r.uniprot_accession) return "—";
        return r.source_url ? (
          <a
            href={r.source_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-[color:var(--hf-accent)] underline underline-offset-2"
          >
            {r.uniprot_accession}
          </a>
        ) : (
          r.uniprot_accession
        );
      },
    },
    {
      id: "opentargets_score",
      header: "Open Targets score",
      cell: ({ row }) => formatSig(row.original.opentargets_score),
    },
    {
      id: "tag",
      header: "",
      cell: ({ row }) => tagBadge(row.original.tag),
    },
    {
      id: "actions",
      header: "",
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`Remove ${row.original.gene_symbol}`}
          onClick={() => edit.mutate({ add: [], remove: [row.original.target_id] })}
          disabled={atMinEntities(effectiveCount)}
          title={
            atMinEntities(effectiveCount)
              ? "Keep at least one target before removing another."
              : undefined
          }
        >
          ✕
        </Button>
      ),
    },
  ];

  return (
    <section className="flex flex-col gap-6">
      {/* Editorial header */}
      <div className="flex flex-col gap-1">
        <Eyebrow>Step 4</Eyebrow>
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="hf-heading-serif">
            Step 4: Disease Targets
            {isUserProvided && (
              <Badge variant="outline" className="ml-2 align-middle text-xs font-normal">
                Provided by you
              </Badge>
            )}
          </h2>
        </div>
        <StageEntityContext data={data} side="disease" />
      </div>

      <StageDataSources stage={4} userProvided={isUserProvided} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <div
          className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
          aria-label={`${stage4.count} targets`}
        >
          <span className="hf-num text-2xl font-semibold tabular-nums">{stage4.count}</span>
          <span className="text-muted-foreground text-xs">targets</span>
        </div>
        {!isUserProvided && (
          <div
            className="bg-card flex min-w-[96px] flex-col items-center rounded-lg border px-4 py-3 shadow-sm"
            aria-label={`min score ${stage4.min_score_applied}`}
          >
            <span className="hf-num text-muted-foreground text-2xl font-semibold tabular-nums">
              {stage4.min_score_applied}
            </span>
            <span className="text-muted-foreground text-xs">min score</span>
          </div>
        )}
      </div>

      {stage4.count === 0 && (
        <p className={cn("text-sm", "[color:var(--hf-fg-3)]")} role="status">
          No disease targets match this score. Lower the minimum score, run this step again, or add
          targets manually.
        </p>
      )}

      {/* Disease-targets table card */}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2">
              <label htmlFor="t4-page-size" className="text-muted-foreground text-sm">
                Rows per page
              </label>
              <select
                id="t4-page-size"
                className="bg-background rounded border px-2 py-1 text-sm"
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
            </div>
            <CsvDownloadButton
              header={S4_CSV_HEADER}
              rows={csvRows}
              filename="disease-targets.csv"
              label="Download CSV"
            />
          </div>
        </CardHeader>
        <CardContent className="px-0">
          <div className="table-wrapper">
            <DataTable columns={columns} data={visibleRows} />
          </div>
        </CardContent>

        {/* Pagination */}
        {pageSize !== "all" && totalPages > 1 && (
          <div className="flex items-center justify-center gap-3 px-6 pb-4">
            <button
              className="hf-btn text-sm"
              disabled={currentPage === 0}
              onClick={() => setPage((p) => p - 1)}
            >
              Previous
            </button>
            <span className="text-muted-foreground text-sm">
              Page {currentPage + 1} / {totalPages}
            </span>
            <button
              className="hf-btn text-sm"
              disabled={currentPage >= totalPages - 1}
              onClick={() => setPage((p) => p + 1)}
            >
              Next
            </button>
          </div>
        )}
      </Card>

      {/* Disease-target add (the table above owns remove) */}
      <EntityAddControl current={effectiveCount} cap={MAX_TARGETS}>
        <TargetValidateBox
          label="Add disease targets"
          onResolved={handleAddTargets}
          showAddButton
        />
      </EntityAddControl>

      {/* Already-in-run note */}
      <AlreadyInRunNote
        labels={alreadyInRun.map((t) => t.gene_symbol ?? t.uniprot_accession ?? t.target_id)}
      />

      {dtParams && !isUserProvided && (
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
            ? "Run the updated step before continuing."
            : "No disease targets found. Lower the minimum score, run this step again, or add one to continue."
        }
        pending={advance.isPending}
        onApprove={() => advance.mutate()}
      />

      {/* Footer */}
      <p className="text-muted-foreground text-sm">
        Disease targets: Open Targets (database snapshot). Human targets only (9606).
      </p>
    </section>
  );
}
