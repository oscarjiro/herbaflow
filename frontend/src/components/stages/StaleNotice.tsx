import { useMutation, useQueryClient } from "@tanstack/react-query";
import { resetFrom } from "../../api/sdk.gen";

/**
 * StaleNotice — shown over a stage whose results are out-of-date because an
 * earlier stage was edited. Re-running is the ONLY thing that recomputes (edits
 * never auto-recompute); it re-runs from the recorded edit origin (`fromStage`).
 *
 * resetFrom requires both `path` and `body` (body.parameters is optional).
 */
export function StaleNotice({ analysisId, fromStage }: { analysisId: string; fromStage: number }) {
  const qc = useQueryClient();
  const rerun = useMutation({
    mutationFn: async () =>
      resetFrom({ path: { analysis_id: analysisId, stage: fromStage }, body: {} }),
    onSuccess: () => qc.invalidateQueries(),
  });
  return (
    <div className="hf-stale" role="status">
      <p>These results are out of date — an earlier step changed.</p>
      <button
        className="hf-btn hf-btn-primary"
        onClick={() => rerun.mutate()}
        disabled={rerun.isPending}
      >
        Re-run from Step {fromStage}
      </button>
    </div>
  );
}
