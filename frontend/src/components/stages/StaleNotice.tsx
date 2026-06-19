import { useMutation, useQueryClient } from "@tanstack/react-query";
import { resetFrom } from "../../api/sdk.gen";
import type { Problem } from "../../lib/problem";
import { notifyError, notifyInfo } from "../../lib/toast";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

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
    onSuccess: () => {
      void qc.invalidateQueries();
      notifyInfo(`Re-running from step ${fromStage}`);
    },
    onError: (error) => notifyError(error as Problem),
  });
  return (
    <Card className="border-hf-warning/40 bg-hf-warning-soft/20 w-full" role="status">
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm">These results are out of date. An earlier step changed.</p>
        <Button
          variant="outline"
          className="border-hf-warning text-hf-warning hover:bg-hf-warning/10 shrink-0"
          onClick={() => rerun.mutate()}
          disabled={rerun.isPending}
        >
          Re-run from Step {fromStage}
        </Button>
      </CardContent>
    </Card>
  );
}
