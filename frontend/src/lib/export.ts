/**
 * CSV export utilities for stage result panels.
 *
 * The backend provides full CSV export at GET /analyses/{id}/export/{stage}?format=csv
 * This utility handles the download trigger and column selection.
 */

export interface ExportConfig {
  analysisId: string
  stageNum: number
  /** Column keys to include (empty = all columns) */
  columns?: string[]
  includeHeaders?: boolean
  includeMetadata?: boolean
}

/**
 * Download a stage export as CSV.
 * Uses RFC 4180 CSV with UTF-8 BOM for Excel compatibility.
 */
export async function downloadStageExport(config: ExportConfig): Promise<void> {
  const params = new URLSearchParams({ format: 'csv' })
  if (config.columns?.length) params.set('columns', config.columns.join(','))
  if (config.includeHeaders === false) params.set('headers', 'false')
  if (config.includeMetadata) params.set('metadata', 'true')

  const url = `/api/analyses/${config.analysisId}/export/${config.stageNum}?${params}`
  const response = await fetch(url)
  if (!response.ok) throw new Error(`Export failed: ${response.status} ${response.statusText}`)

  const blob = await response.blob()
  const objectUrl = URL.createObjectURL(blob)
  const anchor = document.createElement('a')
  anchor.href = objectUrl
  anchor.download = `analysis_${config.analysisId}_stage${config.stageNum}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  document.body.removeChild(anchor)
  setTimeout(() => URL.revokeObjectURL(objectUrl), 100)
}
