import { StageHeader } from '@/components/shared/StageHeader'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { StatCard } from '@/components/shared/StatCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { ExportButton } from '@/components/shared/ExportButton'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage7Result, HubGeneResult } from '@/types/api'

const SOURCES = [
  {
    name: 'NetworkX',
    url: 'https://networkx.org/',
    description: 'Graph analysis library used for centrality computation. Degree centrality normalized 0–1 (Freeman 1979): deg(v)/(n−1). Betweenness, closeness, and eigenvector centralities computed with built-in NetworkX algorithms.',
    citation: 'Hagberg AA, Schult DA, Swart PJ (2008). Exploring network structure, dynamics, and function using NetworkX. Proc 7th Python in Science Conf, pp. 11–15.',
  },
]

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
  {
    key: 'degree',
    header: 'Degree Centrality',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'betweenness',
    header: 'Betweenness Centrality',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'closeness',
    header: 'Closeness Centrality',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'eigenvector',
    header: 'Eigenvector Centrality',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'is_hub',
    header: 'Hub',
    render: (v, row) => {
      const isHub = v as boolean
      const isBottleneck = (row as HubGeneResult).is_hub_bottleneck
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

  const hubCount = result.ranked.filter((g) => g.is_hub).length

  return (
    <div className="space-y-6">
      <StageHeader stage={7} name="Hub Gene Analysis" status={status?.status ?? 'complete'} elapsedSeconds={null} />

      <div className="grid grid-cols-3 gap-4">
        <StatCard label="Total Genes" value={result.ranked.length} />
        <StatCard label="Hub Genes" value={hubCount} />
        <StatCard label="Degree Threshold" value={result.threshold_degree} />
      </div>

      <div className="flex justify-end">
        <ExportButton analysisId={analysisId} stage={7} hasCsv={true} />
      </div>

      <DataTable
        data={result.ranked as HubGeneRow[]}
        columns={columns}
        filterPlaceholder="Filter genes..."
        filterKeys={['gene_symbol']}
        rowClassName={(row) =>
          (row as HubGeneResult).is_hub ? 'bg-hf-sage-faint' : ''
        }
      />

      <div className="space-y-1 text-xs text-hf-fg3 font-sans">
        <p>
          <span className="font-medium text-hf-fg2">Hub threshold:</span> degree ≥ {result.threshold_degree} (= µ + σ of degree distribution) ·{' '}
          betweenness ≥ {result.threshold_betweenness?.toFixed(4) ?? '—'} (= µ + σ of betweenness distribution)
        </p>
        <p>
          <span className="font-medium text-hf-fg2">Hub + Bottleneck:</span> gene exceeding BOTH degree and betweenness thresholds — a critical bridge/hub in the network, highest priority for drug target consideration.
        </p>
        <p>
          <span className="font-medium text-hf-fg2">Centrality definitions:</span>{' '}
          <span className="font-medium text-hf-fg2">Degree</span> — normalized connections (0–1): deg(v)/(n−1), Freeman 1979 ·{' '}
          <span className="font-medium text-hf-fg2">Betweenness</span> — fraction of shortest paths passing through the node ·{' '}
          <span className="font-medium text-hf-fg2">Closeness</span> — inverse mean distance to all other nodes ·{' '}
          <span className="font-medium text-hf-fg2">Eigenvector</span> — influence weighted by neighbour influence (analogous to PageRank).
        </p>
      </div>

      <DataSources sources={SOURCES} />
    </div>
  )
}
