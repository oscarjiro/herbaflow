import { useMutation, useQueryClient } from "@tanstack/react-query";
import { resetFrom } from "@/api/sdk.gen";
import type { Problem } from "@/lib/problem";
import { notifyError, notifyInfo } from "@/lib/toast";

/**
 * The one home for a stage's parameter Redo (change this stage's parameters, then reset-from it).
 * Sibling to {@link useResetFrom} (the zero-parameter recompute): this variant carries the edited
 * parameter map for the stage. It was byte-identical across all six param-bearing stage views
 * (Stage 2/3/4/6/7/8) before extraction — same reset-from call, query invalidation, and toasts.
 */
export function useParamRedo<T extends Record<string, unknown>>(analysisId: string, stage: number) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (changed: T) =>
      resetFrom({
        path: { analysis_id: analysisId, stage },
        body: { parameters: { [String(stage)]: changed } },
      }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo(`Re-running from step ${stage}`);
    },
    onError: (error) => notifyError(error as Problem),
  });
}
