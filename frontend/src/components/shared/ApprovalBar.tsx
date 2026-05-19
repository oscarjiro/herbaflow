interface ApprovalBarProps {
  onApprove: () => void
  onReject: () => void
  isLoading?: boolean
}

export function ApprovalBar({ onApprove, onReject, isLoading }: ApprovalBarProps) {
  return (
    <div className="mt-8 flex items-center gap-3 border-t border-hf-border pt-6">
      <button
        onClick={onApprove}
        disabled={isLoading}
        className="rounded-sm bg-hf-fg1 px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-45"
      >
        Approve & Continue
      </button>
      <button
        onClick={onReject}
        disabled={isLoading}
        className="rounded-sm border border-hf-border px-5 py-2 text-sm font-medium text-hf-fg2 hover:bg-hf-surface-2 disabled:opacity-45"
      >
        Reject
      </button>
    </div>
  )
}
