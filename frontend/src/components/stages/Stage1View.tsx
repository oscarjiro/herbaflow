import { useMutation, useQueryClient } from "@tanstack/react-query";
import { editStage } from "../../api/sdk.gen";
import type { ResolvedCompound } from "../../api/types.gen";
import { MAX_COMPOUNDS } from "../../contract";
import { CompoundValidateBox } from "../CompoundValidateBox";
import { EditableEntityList } from "./EditableEntityList";

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

export function Stage1View({ analysisId, stage1 }: { analysisId: string; stage1: Stage1Data }) {
  const qc = useQueryClient();

  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: analysisId, stage: 1 }, body }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const compounds = stage1.compounds ?? [];
  const current = stage1.count ?? compounds.filter((c) => c.tag !== "user-removed").length;
  const isEdited = stage1.state === "user_provided";

  const entities = compounds.map((c) => ({
    id: c.compound_id,
    label: c.canonical_name ?? c.compound_id,
    tag: c.tag,
  }));

  function handleRemove(id: string) {
    edit.mutate({ add: [], remove: [id] });
  }

  function handleAdd(resolved: ResolvedCompound[]) {
    edit.mutate({ add: resolved.map((r) => r.compound_id), remove: [] });
  }

  return (
    <div className="stage1-view">
      <h2>
        Compounds ({current})
        {isEdited && <span className="hf-badge hf-badge--edited"> edited</span>}
      </h2>
      <EditableEntityList
        entities={entities}
        onRemove={handleRemove}
        cap={MAX_COMPOUNDS}
        current={current}
        addControl={
          <CompoundValidateBox label="Add compounds" onResolved={handleAdd} showAddButton />
        }
      />
    </div>
  );
}
