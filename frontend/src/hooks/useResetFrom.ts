import { useMutation, useQueryClient } from "@tanstack/react-query";
import { resetFrom } from "@/api/sdk.gen";
import type { Problem } from "@/lib/problem";
import { notifyError, notifyInfo } from "@/lib/toast";

/**
 * The one home for the reset-from recompute trigger (re-run a run from a stage).
 * `reset-from` is the ONLY thing that recomputes — edits never auto-recompute.
 * Shared by StaleNotice (out-of-date results after an edit) and RunFailedNotice
 * (recover a failed run). Invalidates queries + toasts on success/error.
 */
export function useResetFrom(analysisId: string, stage: number) {
  const qc = useQueryClient();
  return useMutation({
    // throwOnError so a rejected reset-from (e.g. 422) surfaces via onError as a real problem,
    // instead of resolving and firing a false "Re-running…" success toast.
    mutationFn: async () =>
      resetFrom({ path: { analysis_id: analysisId, stage }, body: {}, throwOnError: true }),
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo(`Re-running from step ${stage}`);
    },
    onError: (error) => notifyError(error as Problem),
  });
}
