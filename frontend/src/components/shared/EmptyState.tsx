interface EmptyStateProps {
  message: string
  action?: { label: string; onClick: () => void }
}

export function EmptyState({ message, action }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-16 text-center">
      <p className="text-hf-fg3 font-sans text-sm">{message}</p>
      {action && (
        <button
          onClick={action.onClick}
          className="mt-4 rounded-sm bg-hf-fg1 px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          {action.label}
        </button>
      )}
    </div>
  )
}
