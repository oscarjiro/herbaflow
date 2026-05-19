interface ErrorStateProps {
  message?: string | null
  onNewAnalysis?: () => void
}

export function ErrorState({ message, onNewAnalysis }: ErrorStateProps) {
  return (
    <div className="rounded-lg border border-hf-danger bg-hf-danger-soft p-6">
      <p className="font-sans font-medium text-hf-danger">Analysis failed</p>
      {message && <p className="mt-1 text-sm text-hf-fg2 font-sans">{message}</p>}
      {onNewAnalysis && (
        <button
          onClick={onNewAnalysis}
          className="mt-4 rounded-sm bg-hf-fg1 px-4 py-2 text-sm font-medium text-white hover:opacity-90"
        >
          Start New Analysis
        </button>
      )}
    </div>
  )
}
