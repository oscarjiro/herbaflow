import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage4Result, DiseaseTargetResult } from '@/types/api'

interface Stage4PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

type DiseaseRow = DiseaseTargetResult & Record<string, unknown>

const columns: ColumnDef<DiseaseRow>[] = [
  {
    key: 'gene_symbol',
    header: 'Gene Symbol',
    sortable: true,
    className: 'font-mono',
  },
  {
    key: 'uniprot_id',
    header: 'UniProt ID',
    className: 'font-mono text-hf-fg3',
  },
  {
    key: 'association_score',
    header: 'Open Targets Score',
    sortable: true,
    render: (value) =>
      value != null ? (value as number).toFixed(3) : '—',
  },
  {
    key: 'disease_name',
    header: 'Disease',
    sortable: true,
  },
  {
    key: 'source',
    header: 'Source',
    render: (value) => {
      const label = value === 'db_cache' ? 'Cached' : value === 'open_targets_api' ? 'Live API' : String(value)
      const status = value === 'db_cache' ? 'complete' : 'stage_1_awaiting_approval'
      return <StatusBadge status={status} label={label} />
    },
  },
]

export function Stage4Panel({ stage, analysis, status }: Stage4PanelProps) {
  const result = analysis?.stage_results[`stage_${stage}`] as Stage4Result | null | undefined

  return (
    <div className="space-y-6">
      <StageHeader
        stage={4}
        name="Disease Targets"
        status={status?.status ?? 'complete'}
        elapsedSeconds={null}
      />

      {!result ? (
        <EmptyState message="Stage 4 results not yet available" />
      ) : (
        <>
          <div className="grid grid-cols-1 gap-4 max-w-xs">
            <StatCard label="Disease-Associated Targets" value={result.disease_target_count} />
          </div>

          <DataTable
            data={result.targets as DiseaseRow[]}
            columns={columns}
            filterPlaceholder="Filter targets..."
            filterKeys={['gene_symbol', 'disease_name']}
          />

          <div className="space-y-1 text-xs text-hf-fg3 font-sans">
            <p>
              <span className="font-medium text-hf-fg2">Open Targets score</span> (0–1): overall disease–gene association strength integrating genetic, genomic, and literature evidence.
            </p>
            <p>
              <span className="font-medium text-hf-fg2">Source:</span> <code className="text-hf-fg2">DB cache</code> = pre-fetched Open Targets data (ensures reproducibility); <code className="text-hf-fg2">API</code> = live Open Targets query at analysis time.
            </p>
          </div>
        </>
      )}
    </div>
  )
}
