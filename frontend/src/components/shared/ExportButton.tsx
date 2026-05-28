import { useState } from 'react'
import { downloadStageExport } from '@/lib/export'

export interface ColumnOption {
  key: string
  label: string
}

interface ExportButtonProps {
  analysisId: string
  stage: number
  hasCsv?: boolean
  availableColumns?: ColumnOption[]
}

export function ExportButton({ analysisId, stage, hasCsv, availableColumns }: ExportButtonProps) {
  const [isPending, setIsPending] = useState(false)
  const [showDialog, setShowDialog] = useState(false)
  const [selectedColumns, setSelectedColumns] = useState<Set<string>>(
    () => new Set(availableColumns?.map((c) => c.key) ?? [])
  )
  const [includeMetadata, setIncludeMetadata] = useState(false)

  function handleJsonExport() {
    // JSON export: open URL directly (browser download)
    const url = `/api/analyses/${analysisId}/export/${stage}?format=json`
    window.open(url, '_blank')
  }

  function openCsvDialog() {
    // Reset column selection to all checked whenever dialog opens
    setSelectedColumns(new Set(availableColumns?.map((c) => c.key) ?? []))
    setIncludeMetadata(false)
    setShowDialog(true)
  }

  async function handleCsvExport() {
    setShowDialog(false)
    setIsPending(true)
    try {
      const columns =
        availableColumns && selectedColumns.size < availableColumns.length
          ? [...selectedColumns]
          : undefined
      await downloadStageExport({
        analysisId,
        stageNum: stage,
        columns,
        includeMetadata,
      })
    } finally {
      setIsPending(false)
    }
  }

  function toggleColumn(key: string) {
    setSelectedColumns((prev) => {
      const next = new Set(prev)
      if (next.has(key)) {
        next.delete(key)
      } else {
        next.add(key)
      }
      return next
    })
  }

  const hasColumns = availableColumns && availableColumns.length > 0

  return (
    <>
      <div className="flex gap-2">
        <button
          onClick={handleJsonExport}
          disabled={isPending}
          className="rounded-sm border border-hf-border px-3 py-1.5 text-xs font-medium text-hf-fg2 hover:bg-hf-surface-2 disabled:opacity-45"
        >
          Export JSON
        </button>
        {hasCsv && (
          <button
            onClick={hasColumns ? openCsvDialog : () => downloadStageExport({ analysisId, stageNum: stage }).catch(console.error)}
            disabled={isPending}
            className="rounded-sm border border-hf-border px-3 py-1.5 text-xs font-medium text-hf-fg2 hover:bg-hf-surface-2 disabled:opacity-45"
          >
            {isPending ? 'Exporting…' : 'Export CSV'}
          </button>
        )}
      </div>

      {showDialog && hasColumns && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40"
          role="dialog"
          aria-modal="true"
          aria-label="Export CSV options"
        >
          <div className="w-80 rounded-md border border-hf-border bg-hf-surface p-5 shadow-xl">
            <h2 className="mb-3 text-sm font-semibold text-hf-fg1">Export CSV</h2>

            <p className="mb-2 text-xs text-hf-fg3">Select columns to include:</p>
            <ul className="mb-3 space-y-1.5 max-h-48 overflow-y-auto">
              {availableColumns!.map((col) => (
                <li key={col.key}>
                  <label className="flex cursor-pointer items-center gap-2 text-xs text-hf-fg2">
                    <input
                      type="checkbox"
                      checked={selectedColumns.has(col.key)}
                      onChange={() => toggleColumn(col.key)}
                      className="accent-hf-sage"
                    />
                    {col.label}
                  </label>
                </li>
              ))}
            </ul>

            <label className="flex cursor-pointer items-center gap-2 text-xs text-hf-fg2 mb-4">
              <input
                type="checkbox"
                checked={includeMetadata}
                onChange={(e) => setIncludeMetadata(e.target.checked)}
                className="accent-hf-sage"
              />
              Include metadata row (analysis ID, date, stage params)
            </label>

            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowDialog(false)}
                className="rounded-sm border border-hf-border px-3 py-1.5 text-xs font-medium text-hf-fg2 hover:bg-hf-surface-2"
              >
                Cancel
              </button>
              <button
                onClick={handleCsvExport}
                disabled={selectedColumns.size === 0}
                className="rounded-sm bg-hf-sage px-3 py-1.5 text-xs font-medium text-hf-fg1 hover:opacity-90 disabled:opacity-40"
              >
                Export
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  )
}
