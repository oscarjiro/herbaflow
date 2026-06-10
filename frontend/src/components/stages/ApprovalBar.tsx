/**
 * ApprovalBar — the "Approve & Continue" control for one stage's checkpoint.
 *
 * Renders only when the run is awaiting approval AND this view is the current
 * stage (`currentStage === stage`), so stacked stage views never show more than
 * one Approve button. When `disabled`, the button is inert and `disabledReason`
 * is shown (used for the empty-stage blocking-stop).
 */

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
    <div className="approval-bar">
      <button className="hf-btn hf-btn-primary" onClick={onApprove} disabled={disabled}>
        Approve &amp; Continue
      </button>
      {disabled && disabledReason && (
        <p className="hf-muted" role="status">
          {disabledReason}
        </p>
      )}
    </div>
  );
}
