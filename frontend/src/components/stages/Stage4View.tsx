/**
 * Stage4View — disease → target collection results (DB read of the seeded Open Targets snapshot).
 *
 * Renders:
 *  - Summary count cards: target count + the applied min_score (min_score hidden for user_provided)
 *  - Disease-targets DataTable (one row per target): gene symbol, UniProt accession (linked), Open
 *    Targets score (display-rounded), in-table delete; DataTable-owned pagination;
 *    CSV keyed on gene_symbol + uniprot_accession + opentargets_score + source_url (NEVER a UUID; the
 *    near-constant association_type is kept on the data type but no longer surfaced or exported)
 *  - User-removed rows are hidden from the table AND the CSV (data still persists)
 *  - Target remove via the in-table delete column; add via a standalone EntityAddControl +
 *    TargetValidateBox (editStage stage 4)
 *  - ParamPanel (min_score) + Redo (resetFrom stage 4) — both the ParamPanel and the min-score card
 *    are hidden for user_provided; at count 0 a status note explains the blocking-stop; recover via
 *    Redo or a manual add
 *  - Footer: "Disease targets: Open Targets (database snapshot). Human targets only (9606)."
 *
 * The stage header, ApprovalBar, and StaleNotice are owned by the StageView shell.
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

import { useMemo } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import type { AnalysisRead, ResolvedTarget } from "../../api/types.gen";
import { resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import {
  DISEASE_TARGETS_NUMERIC_PARAMS,
  DISEASE_TARGETS_PARAMS,
  MAX_TARGETS,
} from "../../contract";
import { atMinEntities, isUserRemoved } from "../../lib/entities";
import { formatSig, formatCount } from "../../lib/format";
import { stageLabel } from "../../contract/labels";
import { uniprotUrl } from "../../lib/externalUrls";
import { useAddWithDedup } from "../../hooks/useAddWithDedup";
import { useStageEntityEdit } from "../../hooks/useStageEntityEdit";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataTable } from "@/components/ui/DataTable";
import { CsvDownloadButton } from "@/components/ui/CsvDownloadButton";
import { ExternalLink } from "@/components/ui/ExternalLink";
import { AlreadyInRunNote } from "./AlreadyInRunNote";
import { EntityAddControl } from "./EntityAddControl";
import { ParamPanel } from "./ParamPanel";
import { isRunBusy } from "@/lib/runStatus";
import { StageDataSources } from "./StageDataSources";
import { StageEntityContext } from "./StageEntityContext";
import { StageSummaryCard } from "./StageSummaryCard";
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

export function Stage4View({ data }: { data: AnalysisRead }) {
  const stage4 = data.stage_results?.["4"] as Stage4Result | undefined;
  const stageState = (data as { stage_state?: Record<string, string> }).stage_state?.["4"];
  const dtParams = (data.parameters as Record<string, unknown> | undefined)?.disease_targets as
    | Record<string, number | boolean>
    | undefined;

  const qc = useQueryClient();
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
  const edit = useStageEntityEdit({
    analysisId: data.analysis_id,
    stage: 4,
    entity: { singular: "target", plural: "targets" },
  });

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
        <h2>{stageLabel(4)}</h2>
        <p className={cn("text-sm", "[color:var(--hf-fg-3)]")}>Not applicable for this run.</p>
      </section>
    );
  }

  const effectiveCount = stage4.targets.filter((t) => t.tag !== "user-removed").length;

  const isUserProvided = stageState === "user_provided";

  // Per-target column definitions — spec-aligned columns in the required order.
  const columns: ColumnDef<Row>[] = [
    // 1. UniProt accession → ExternalLink to UniProt entry page.
    {
      id: "uniprot",
      accessorFn: (row) => row.uniprot_accession ?? "",
      header: "UniProt",
      meta: { className: "font-mono" },
      cell: ({ row }) => {
        const acc = row.original.uniprot_accession;
        if (!acc) return <span className="text-hf-fg-3">—</span>;
        return (
          <ExternalLink href={uniprotUrl(acc)} className="font-mono">
            {acc}
          </ExternalLink>
        );
      },
    },
    // 2. Gene symbol.
    {
      id: "gene_symbol",
      accessorFn: (row) => row.gene_symbol ?? "",
      header: "Gene symbol",
      cell: ({ row }) => row.original.gene_symbol,
    },
    // 3. Open Targets score — HIDDEN when stage_state === "user_provided" (manual runs have no score).
    ...(isUserProvided
      ? []
      : ([
          {
            id: "opentargets_score",
            header: "Open Targets score",
            meta: { className: "num" },
            cell: ({ row }: { row: { original: Row } }) =>
              formatSig(row.original.opentargets_score),
          },
        ] as ColumnDef<Row>[])),
    // 4. × delete — reuses the existing edit mutation's remove path.
    {
      id: "actions",
      header: "",
      enableSorting: false,
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
      <StageEntityContext data={data} side="disease" />

      <StageDataSources stage={4} userProvided={isUserProvided} />

      {/* Summary cards */}
      <div className="flex flex-wrap gap-3">
        <StageSummaryCard
          value={formatCount(stage4.count)}
          label="targets"
          ariaLabel={`${stage4.count} targets`}
        />
        {!isUserProvided && (
          <StageSummaryCard
            value={stage4.min_score_applied}
            label="min score"
            ariaLabel={`min score ${stage4.min_score_applied}`}
            muted
          />
        )}
      </div>

      {/* Disease-targets table card */}
      {isUserProvided && (
        <div>
          <Badge variant="secondary">Provided by you</Badge>
        </div>
      )}
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-3">
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
            <DataTable columns={columns} data={rows} />
          </div>
        </CardContent>
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
          disabled={redo.isPending || isRunBusy(data.status)}
          onRedo={(changed) => redo.mutate(changed)}
        />
      )}

      {/* Footer */}
      <p className="text-muted-foreground text-sm">
        Disease targets: Open Targets (database snapshot). Human targets only (9606).
      </p>
    </section>
  );
}
