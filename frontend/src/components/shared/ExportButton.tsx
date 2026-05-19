import { useExportStage } from '@/hooks/useExportStage'

interface ExportButtonProps {
  analysisId: string
  stage: number
  hasCsv?: boolean
}

export function ExportButton({ analysisId, stage, hasCsv }: ExportButtonProps) {
  const { mutate, isPending } = useExportStage()
  return (
    <div className="flex gap-2">
      <button
        onClick={() => mutate({ id: analysisId, stage, format: 'json' })}
        disabled={isPending}
        className="rounded-sm border border-hf-border px-3 py-1.5 text-xs font-medium text-hf-fg2 hover:bg-hf-surface-2 disabled:opacity-45"
      >
        Export JSON
      </button>
      {hasCsv && (
        <button
          onClick={() => mutate({ id: analysisId, stage, format: 'csv' })}
          disabled={isPending}
          className="rounded-sm border border-hf-border px-3 py-1.5 text-xs font-medium text-hf-fg2 hover:bg-hf-surface-2 disabled:opacity-45"
        >
          Export CSV
        </button>
      )}
    </div>
  )
}
