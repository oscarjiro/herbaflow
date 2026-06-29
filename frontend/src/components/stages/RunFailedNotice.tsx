import { useResetFrom } from "@/hooks/useResetFrom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * RunFailedNotice — shown when a run's status is "failed" (the backend crashed or
 * restarted mid-stage, or a stage hit an unrecoverable error). It names the step
 * that failed, shows the backend's reason, and offers the single recovery: re-run
 * from the failed step (reset-from), which recomputes that stage onward while the
 * completed earlier stages are preserved. Mirrors StaleNotice's reset-from wiring.
 */
export function RunFailedNotice({
  analysisId,
  failedStage,
  message,
}: {
  analysisId: string;
  failedStage: number;
  message?: string | null;
}) {
  const rerun = useResetFrom(analysisId, failedStage);
  return (
    <Card className="border-hf-danger/50 bg-hf-danger-soft/20 w-full" role="alert">
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="flex flex-col gap-1">
          <p className="text-hf-fg-1 text-sm font-medium">Step {failedStage} failed.</p>
          {message ? <p className="text-hf-fg-3 text-sm">{message}</p> : null}
        </div>
        <Button
          variant="danger"
          className="shrink-0"
          onClick={() => rerun.mutate()}
          disabled={rerun.isPending}
        >
          Re-run from Step {failedStage}
        </Button>
      </CardContent>
    </Card>
  );
}
