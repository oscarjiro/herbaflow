import { useMutation, useQueryClient } from "@tanstack/react-query";
import { getAnalysisOptions } from "../api/@tanstack/react-query.gen";
import { editStage } from "../api/sdk.gen";
import type { AnalysisRead } from "../api/types.gen";
import { markEntitiesRemoved } from "../lib/optimisticEdit";
import type { Problem } from "../lib/problem";
import { notifyError, notifySuccess } from "../lib/toast";

type EditBody = { add: string[]; remove: string[] };

type EntityCopy = {
  singular: string;
  plural: string;
};

function label(count: number, copy: EntityCopy): string {
  return `${count} ${count === 1 ? copy.singular : copy.plural}`;
}

function successMessage(body: EditBody, copy: EntityCopy): string | null {
  if (body.add.length > 0) return `Added ${label(body.add.length, copy)}`;
  if (body.remove.length > 0) return `Removed ${label(body.remove.length, copy)}`;
  return null;
}

function rollbackProblem(body: EditBody, copy: EntityCopy): Problem {
  return {
    title: `Could not remove ${body.remove.length === 1 ? copy.singular : copy.plural}. Your list was restored.`,
  };
}

export function useStageEntityEdit({
  analysisId,
  stage,
  entity,
}: {
  analysisId: string;
  stage: 1 | 3 | 4;
  entity: EntityCopy;
}) {
  const qc = useQueryClient();
  const key = getAnalysisOptions({ path: { analysis_id: analysisId } }).queryKey;

  return useMutation({
    mutationFn: (body: EditBody) => editStage({ path: { analysis_id: analysisId, stage }, body }),
    onMutate: async (body) => {
      if (body.remove.length === 0) return { prev: undefined };
      await qc.cancelQueries({ queryKey: key });
      const prev = qc.getQueryData<AnalysisRead>(key);
      if (prev) qc.setQueryData<AnalysisRead>(key, markEntitiesRemoved(prev, stage, body.remove));
      return { prev };
    },
    onSuccess: (_result, body) => {
      const message = successMessage(body, entity);
      if (message) notifySuccess(message);
    },
    onError: (error, body, ctx) => {
      if (ctx?.prev) qc.setQueryData(key, ctx.prev);
      if (body.remove.length > 0) {
        notifyError(rollbackProblem(body, entity));
        return;
      }
      notifyError(error as Problem);
    },
    onSettled: () => qc.invalidateQueries(),
  });
}
