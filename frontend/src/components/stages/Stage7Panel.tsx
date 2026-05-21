import { StageHeader } from '@/components/shared/StageHeader'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { StatCard } from '@/components/shared/StatCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { ExportButton } from '@/components/shared/ExportButton'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage7Result, HubGeneResult } from '@/types/api'

interface Stage7PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

type HubGeneRow = HubGeneResult & Record<string, unknown>

const columns: ColumnDef<HubGeneRow>[] = [
  { key: 'rank', header: 'Rank', sortable: true },
  { key: 'gene_symbol', header: 'Gene', sortable: true },
  { key: 'degree', header: 'Degree', sortable: true },
  {
    key: 'betweenness_centrality',
    header: 'Betweenness',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'closeness_centrality',
    header: 'Closeness',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'eigenvector_centrality',
    header: 'Eigenvector',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'is_hub',
    header: 'Hub',
    render: (v, row) => {
      const isHub = v as boolean
      const isBottleneck = (row as HubGeneResult).is_bottleneck
      if (isHub && isBottleneck) {
        return (
          <span className="px-1.5 py-0.5 rounded text-xs bg-hf-sage text-hf-bg font-medium">
            Hub + Bottleneck
          </span>
        )
      }
      if (isHub) {
        return (
          <span className="px-1.5 py-0.5 rounded text-xs bg-hf-sage-soft text-hf-sage-deep font-medium">
            Hub
          </span>
        )
      }
      return null
    },
  },
]

export function Stage7Panel({ stage, analysis, status, analysisId }: Stage7PanelProps) {
  const result = analysis?.stage_results[`stage_${stage}`] as Stage7Result | null | undefined

  if (!result) {
    return (
      <div className="space-y-6">
        <StageHeader stage={7} name="Hub Gene Analysis" status={status?.status ?? 'pending'} elapsedSeconds={null} />
        <EmptyState message="Stage 7 results not yet available" />
      </div>
    )
  }

  const hubCount = result.hub_genes.filter((g) => g.is_hub).length

  return (
    <div className="space-y-6">
      <StageHeader stage={7} name="Hub Gene Analysis" status={status?.status ?? 'complete'} elapsedSeconds={null} />

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total Genes" value={result.hub_genes.length} />
        <StatCard label="Hub Genes" value={hubCount} />
        <StatCard label="Degree Threshold" value={result.threshold_degree} />
      </div>

      <div className="flex justify-end">
        <ExportButton analysisId={analysisId} stage={7} hasCsv={true} />
      </div>

      <DataTable
        data={result.hub_genes as HubGeneRow[]}
        columns={columns}
        filterPlaceholder="Filter genes..."
        filterKeys={['gene_symbol']}
        rowClassName={(row) =>
          (row as HubGeneResult).is_hub ? 'bg-hf-sage-faint' : ''
        }
      />

      <p className="text-xs text-hf-fg4">
        Hub threshold: degree ≥ {result.threshold_degree} · betweenness ≥ {result.threshold_betweenness?.toFixed(4) ?? '—'}
      </p>
    </div>
  )
}
