/**
 * ApprovalBar — the "Approve & Continue" control for one stage's checkpoint.
 *
 * Renders only when the run is awaiting approval AND this view is the current
 * stage (`currentStage === stage`), so stacked stage views never show more than
 * one Approve button. When `disabled`, the button is inert and `disabledReason`
 * is shown (used for the empty-stage blocking-stop).
 */

import { Button } from "@/components/ui/button";

export function ApprovalBar({
  stage,
  status,
  currentStage,
  onApprove,
  disabled = false,
  disabledReason,
}: {
  stage: number;
  status: string | null | undefined;
  currentStage: number | null | undefined;
  onApprove: () => void;
  disabled?: boolean;
  disabledReason?: string;
}) {
  if (!status || currentStage == null) return null;
  if (currentStage !== stage) return null;
  if (status !== `stage_${stage}_awaiting_approval`) return null;

  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <Button onClick={onApprove} disabled={disabled}>
        Approve &amp; Continue
      </Button>
      {disabled && disabledReason && (
        <p className="text-muted-foreground text-sm" role="status">
          {disabledReason}
        </p>
      )}
    </div>
  );
}
