import { useResetFrom } from "@/hooks/useResetFrom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

/**
 * StaleNotice — shown over a stage whose results are out-of-date because an
 * earlier stage was edited. Re-running is the ONLY thing that recomputes (edits
 * never auto-recompute); it re-runs from the recorded edit origin (`fromStage`).
 *
 * resetFrom requires both `path` and `body` (body.parameters is optional).
 */
export function StaleNotice({
  analysisId,
  fromStage,
  disabled = false,
}: {
  analysisId: string;
  fromStage: number;
  /** Disabled while the run is busy computing a stage (no redo/re-run mid-run). */
  disabled?: boolean;
}) {
  const rerun = useResetFrom(analysisId, fromStage);
  return (
    <Card className="border-hf-warning/40 bg-hf-warning-soft/20 w-full" role="status">
      <CardContent className="flex flex-col gap-3 py-4 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm">These results are out of date. An earlier step changed.</p>
        <Button
          variant="warning"
          className="shrink-0"
          onClick={() => rerun.mutate()}
          disabled={rerun.isPending || disabled}
        >
          Re-run from Step {fromStage}
        </Button>
      </CardContent>
    </Card>
  );
}
