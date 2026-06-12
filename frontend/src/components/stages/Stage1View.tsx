import { useCallback, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { editStage } from "../../api/sdk.gen";
import type { ResolvedCompound } from "../../api/types.gen";
import { MAX_COMPOUNDS } from "../../contract";
import { CompoundValidateBox } from "../CompoundValidateBox";
import { EditableEntityList } from "./EditableEntityList";
import { StageDataSources } from "./StageDataSources";

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

  // Hooks must be called unconditionally before any early return.
  const edit = useMutation({
    mutationFn: (body: { add: string[]; remove: string[] }) =>
      editStage({ path: { analysis_id: analysisId, stage: 1 }, body }),
    onSuccess: () => qc.invalidateQueries(),
  });

  const [alreadyInRun, setAlreadyInRun] = useState<ResolvedCompound[]>([]);

  if (stage1.state === "not_applicable") {
    return (
      <section className="stage-view stage-view--na" aria-disabled>
        <h2>Step 1 — Compounds</h2>
        <p className="hf-muted">Not applicable for this run.</p>
      </section>
    );
  }

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

  const handleAdd = useCallback(
    (resolved: ResolvedCompound[]) => {
      const currentIds = new Set((stage1.compounds ?? []).map((c) => c.compound_id));
      const already = resolved.filter((r) => currentIds.has(r.compound_id));
      const fresh = resolved.filter((r) => !currentIds.has(r.compound_id));
      setAlreadyInRun(already);
      if (fresh.length > 0) {
        edit.mutate({ add: fresh.map((r) => r.compound_id), remove: [] });
      }
    },
    [stage1.compounds, edit],
  );

  return (
    <div className="stage1-view">
      <h2>
        Step 1 — Compounds ({current})
        {isEdited && <span className="hf-badge hf-badge--edited"> edited</span>}
        {stage1.state === "user_provided" && (
          <span className="hf-badge hf-badge--provided"> Provided by you</span>
        )}
      </h2>
      <StageDataSources stage={1} />
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
      {alreadyInRun.length > 0 && (
        <p className="hf-muted" role="status">
          {alreadyInRun.length} already in run:{" "}
          {alreadyInRun.map((c) => c.canonical_name ?? c.canonical_key ?? c.compound_id).join(", ")}
        </p>
      )}
    </div>
  );
}
