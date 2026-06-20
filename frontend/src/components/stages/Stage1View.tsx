import { useMutation, useQueryClient } from "@tanstack/react-query";
import type { ColumnDef } from "@tanstack/react-table";
import { getAnalysisOptions } from "../../api/@tanstack/react-query.gen";
import { editStage } from "../../api/sdk.gen";
import type { AnalysisRead, ResolvedCompound } from "../../api/types.gen";
import { MAX_COMPOUNDS } from "../../contract";
import { markEntitiesRemoved } from "../../lib/optimisticEdit";
import type { Problem } from "../../lib/problem";
import { notifyError } from "../../lib/toast";
import { useAddWithDedup } from "../../hooks/useAddWithDedup";
import { atMinEntities, isUserRemoved } from "../../lib/entities";
import { cn } from "@/lib/cn";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader } from "@/components/ui/card";
import { DataTable } from "@/components/ui/DataTable";
import { Separator } from "@/components/ui/separator";
import { Eyebrow } from "@/components/ui/editorial";
import { CompoundValidateBox } from "../CompoundValidateBox";
import { AlreadyInRunNote } from "./AlreadyInRunNote";
import { EntityAddControl } from "./EntityAddControl";
import { StageDataSources } from "./StageDataSources";
import { StageEntityContext } from "./StageEntityContext";

type Stage1Compound = {
  compound_id: string;
  canonical_name?: string | null;
  tag?: string;
};

type Stage1Data = {
  count?: number;
  compounds?: Stage1Compound[];
  state?: string;
};

type Stage1Row = {
  id: string;
  label: string;
  tag?: string;
};

export function Stage1View({ data }: { data: AnalysisRead }) {
  const stage1 = (data.stage_results?.["1"] ?? {}) as Stage1Data;
  const analysisId = data.analysis_id;
  const stageState = (data as { stage_state?: Record<string, string> }).stage_state?.["1"];

  const qc = useQueryClient();

  // Hooks must be called unconditionally before any early return.
  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: analysisId, stage: 1 }, body }),
    onMutate: async (body) => {
      if (body.remove.length === 0) return { prev: undefined };
      const key = getAnalysisOptions({ path: { analysis_id: analysisId } }).queryKey;
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<AnalysisRead>(key);
      if (prev) qc.setQueryData<AnalysisRead>(key, markEntitiesRemoved(prev, 1, body.remove));
      return { prev };
    },
    onError: (error, _body, ctx) => {
      const key = getAnalysisOptions({ path: { analysis_id: analysisId } }).queryKey;
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      notifyError(error as Problem);
    },
    onSettled: () => qc.invalidateQueries(),
  });

  const currentCompoundIds = new Set((stage1.compounds ?? []).map((c) => c.compound_id));
  const { alreadyInRun, handleAdd } = useAddWithDedup<ResolvedCompound>({
    currentIds: currentCompoundIds,
    getId: (r) => r.compound_id,
    onAddIds: (ids) => edit.mutate({ add: ids, remove: [] }),
  });

  if (stageState === "not_applicable") {
    return (
      <section className="stage-view stage-view--na" aria-disabled>
        <h2>Step 1: Compounds</h2>
        <p className={cn("text-sm", "[color:var(--hf-fg-3)]")}>Not applicable for this run.</p>
      </section>
    );
  }

  const isUserProvided = stageState === "user_provided";

  const compounds = stage1.compounds ?? [];
  const current = stage1.count ?? compounds.filter((c) => c.tag !== "user-removed").length;
  const atMin = atMinEntities(current);

  const rows: Stage1Row[] = compounds
    .filter((c) => !isUserRemoved(c.tag))
    .map((c) => ({
      id: c.compound_id,
      label: c.canonical_name ?? c.compound_id,
      tag: c.tag,
    }));

  function handleRemove(id: string) {
    edit.mutate({ add: [], remove: [id] });
  }

  const columns: ColumnDef<Stage1Row>[] = [
    {
      accessorKey: "label",
      header: "Compound",
    },
    {
      id: "provenance",
      header: "Source",
      enableSorting: false,
      cell: ({ row }) =>
        row.original.tag === "user-added" ? <Badge variant="secondary">Added by you</Badge> : null,
    },
    {
      id: "actions",
      header: "",
      enableSorting: false,
      cell: ({ row }) => (
        <Button
          variant="ghost"
          size="icon-xs"
          aria-label={`Remove ${row.original.label}`}
          onClick={() => handleRemove(row.original.id)}
          disabled={atMin}
          title={atMin ? "A stage must keep at least one entry." : undefined}
        >
          ✕
        </Button>
      ),
    },
  ];

  return (
    <section className="flex flex-col gap-4">
      {/* Editorial header */}
      <div className="flex flex-col gap-1">
        <Eyebrow>Step 1</Eyebrow>
        <div className="flex flex-wrap items-baseline gap-2">
          <h2 className="hf-heading-serif">Step 1: Compounds ({current})</h2>
        </div>
      </div>

      <Separator className="opacity-50" />

      {/* Context + sources */}
      <div className="flex flex-col gap-1">
        <StageEntityContext data={data} side="plant" />
        <StageDataSources stage={1} userProvided={isUserProvided} />
      </div>

      {/* Compound list card */}
      {isUserProvided && (
        <div>
          <Badge variant="secondary">Provided by you</Badge>
        </div>
      )}
      <Card>
        <CardHeader className="pb-0" />
        <CardContent className="flex flex-col gap-3 pt-0">
          <div className="table-wrapper">
            <DataTable columns={columns} data={rows} emptyMessage="No compounds yet." />
          </div>
          <EntityAddControl current={current} cap={MAX_COMPOUNDS}>
            <CompoundValidateBox label="Add compounds" onResolved={handleAdd} showAddButton />
          </EntityAddControl>
          <AlreadyInRunNote
            labels={alreadyInRun.map((c) => c.canonical_name ?? c.canonical_key ?? c.compound_id)}
          />
        </CardContent>
      </Card>
    </section>
  );
}
