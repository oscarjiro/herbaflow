import { useMutation, useQueryClient } from "@tanstack/react-query";
import { editStage } from "../../api/sdk.gen";
import type { AnalysisRead, ResolvedCompound } from "../../api/types.gen";
import { MAX_COMPOUNDS } from "../../contract";
import { useAddWithDedup } from "../../hooks/useAddWithDedup";
import { CompoundValidateBox } from "../CompoundValidateBox";
import { AlreadyInRunNote } from "./AlreadyInRunNote";
import { EditableEntityList } from "./EditableEntityList";
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

export function Stage1View({ data }: { data: AnalysisRead }) {
  const stage1 = (data.stage_results?.["1"] ?? {}) as Stage1Data;
  const analysisId = data.analysis_id;
  const stageState = (data as { stage_state?: Record<string, string> }).stage_state?.["1"];

  const qc = useQueryClient();

  // Hooks must be called unconditionally before any early return.
  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: analysisId, stage: 1 }, body }),
    onSuccess: () => qc.invalidateQueries(),
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
        <h2>Step 1 — Compounds</h2>
        <p className="hf-muted">Not applicable for this run.</p>
      </section>
    );
  }

  const compounds = stage1.compounds ?? [];
  const current = stage1.count ?? compounds.filter((c) => c.tag !== "user-removed").length;

  const entities = compounds.map((c) => ({
    id: c.compound_id,
    label: c.canonical_name ?? c.compound_id,
    tag: c.tag,
  }));

  function handleRemove(id: string) {
    edit.mutate({ add: [], remove: [id] });
  }

  return (
    <div className="stage1-view">
      <h2>
        Step 1 — Compounds ({current})
        {stageState === "user_provided" && (
          <span className="hf-badge hf-badge--provided"> Provided by you</span>
        )}
      </h2>
      <StageDataSources stage={1} />
      <StageEntityContext data={data} side="plant" />
      <EditableEntityList
        entities={entities}
        onRemove={handleRemove}
        cap={MAX_COMPOUNDS}
        current={current}
        addControl={
          <CompoundValidateBox label="Add compounds" onResolved={handleAdd} showAddButton />
        }
      />

      {/* Already-in-run note */}
      <AlreadyInRunNote
        labels={alreadyInRun.map((c) => c.canonical_name ?? c.canonical_key ?? c.compound_id)}
      />
    </div>
  );
}
