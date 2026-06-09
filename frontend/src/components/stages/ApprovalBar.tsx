/**
 * ApprovalBar — shows the "Approve & Continue" button only when the run is
 * awaiting approval for the given stage.  Renders nothing otherwise.
 *
 * Visibility rule: status === `stage_${currentStage}_awaiting_approval`
 */

export function ApprovalBar({
  status,
  currentStage,
  onApprove,
}: {
  status: string | null | undefined;
  currentStage: number | null | undefined;
  onApprove: () => void;
}) {
  if (!status || currentStage == null) return null;
  const expected = `stage_${currentStage}_awaiting_approval`;
  if (status !== expected) return null;

  return (
    <div className="approval-bar">
      <button className="hf-btn hf-btn-primary" onClick={onApprove}>
        Approve &amp; Continue
      </button>
    </div>
  );
}
