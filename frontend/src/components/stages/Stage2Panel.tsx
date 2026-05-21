import { useState } from 'react'
import { StageHeader } from '@/components/shared/StageHeader'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { cn } from '@/lib/utils'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage2Result, AdmeCompoundResult } from '@/types/api'

interface Stage2PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

type FilterMode = 'all' | 'passed' | 'failed'

type AdmeRow = AdmeCompoundResult & Record<string, unknown>

const columns: ColumnDef<AdmeRow>[] = [
  {
    key: 'canonical_name',
    header: 'Compound Name',
    sortable: true,
  },
  {
    key: 'adme_pass',
    header: 'ADME Result',
    render: (value) => (
      <StatusBadge
        status={value ? 'complete' : 'failed'}
        label={value ? 'Pass' : 'Fail'}
      />
    ),
  },
  {
    key: 'is_np_exception',
    header: 'NP Exception',
    render: (value) => (
      <StatusBadge
        status={value ? 'stage_1_awaiting_approval' : 'neutral'}
        label={value ? 'Yes' : 'No'}
      />
    ),
  },
]

export function Stage2Panel({ stage, analysis, status }: Stage2PanelProps) {
  const result = analysis?.stage_results[`stage_${stage}`] as Stage2Result | null | undefined
  const [filterMode, setFilterMode] = useState<FilterMode>('all')

  const total = result ? result.passed + result.failed : 0
  const passedPct = total > 0 ? (((result?.passed ?? 0) / total) * 100).toFixed(1) : '0.0'
  const failedPct = total > 0 ? (((result?.failed ?? 0) / total) * 100).toFixed(1) : '0.0'

  const filteredCompounds: AdmeRow[] = result
    ? (filterMode === 'passed'
      ? result.compounds.filter(c => c.adme_pass)
      : filterMode === 'failed'
        ? result.compounds.filter(c => !c.adme_pass)
        : result.compounds) as AdmeRow[]
    : []

  const filterBtnBase = 'px-3 py-1 text-xs rounded-sm font-sans transition-colors'
  const filterBtnActive = 'bg-hf-fg1 text-hf-bg'
  const filterBtnInactive = 'bg-hf-surface border border-hf-border text-hf-fg2 hover:text-hf-fg1'

  return (
    <div className="space-y-6">
      <StageHeader
        stage={2}
        name="ADME Screening"
        status={status?.status ?? 'complete'}
        elapsedSeconds={null}
      />

      {!result ? (
        <EmptyState message="Stage 2 results not yet available" />
      ) : (
        <>
          <div className="flex gap-4">
            <div className="rounded-lg bg-hf-success-soft px-5 py-3 flex-1">
              <p className="text-xs font-sans text-hf-success">Passed</p>
              <p className="mt-1 text-xl font-display text-hf-success">
                {result.passed}
                <span className="ml-2 text-sm font-sans">{passedPct}%</span>
              </p>
            </div>
            <div className="rounded-lg bg-hf-danger-soft px-5 py-3 flex-1">
              <p className="text-xs font-sans text-hf-danger">Failed</p>
              <p className="mt-1 text-xl font-display text-hf-danger">
                {result.failed}
                <span className="ml-2 text-sm font-sans">{failedPct}%</span>
              </p>
            </div>
            <div className="rounded-lg bg-hf-warning-soft px-5 py-3 flex-1">
              <p className="text-xs font-sans text-hf-warning">NP Exceptions</p>
              <p className="mt-1 text-xl font-display text-hf-warning">{result.np_exceptions}</p>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs text-hf-fg3 font-sans">Show:</span>
            {(['all', 'passed', 'failed'] as FilterMode[]).map(mode => (
              <button
                key={mode}
                onClick={() => setFilterMode(mode)}
                className={cn(filterBtnBase, filterMode === mode ? filterBtnActive : filterBtnInactive)}
              >
                {mode.charAt(0).toUpperCase() + mode.slice(1)}
              </button>
            ))}
          </div>

          <DataTable
            data={filteredCompounds}
            columns={columns}
            filterPlaceholder="Filter compounds..."
            filterKeys={['canonical_name']}
          />
        </>
      )}
    </div>
  )
}
