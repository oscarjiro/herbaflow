import { StageHeader } from '@/components/shared/StageHeader'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { StatCard } from '@/components/shared/StatCard'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { SkippedStageNotice } from '@/components/shared/SkippedStageNotice'
import { ExportButton } from '@/components/shared/ExportButton'
import { StageParamsPanel } from '@/components/shared/StageParamsPanel'
import { isSkippedStage } from '@/types/api'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage7Result, HubGeneResult, CommunityHubGene } from '@/types/api'

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
type CommunityHubRow = CommunityHubGene & Record<string, unknown>

const communityColumns: ColumnDef<CommunityHubRow>[] = [
  { key: 'gene_symbol', header: 'Gene', sortable: true },
  {
    key: 'community_degree',
    header: 'Degree',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'community_betweenness',
    header: 'Betweenness',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'community_closeness',
    header: 'Closeness',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
  {
    key: 'community_eigenvector',
    header: 'Eigenvector',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(4) : '—',
  },
]

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
  // analysisId used by StageParamsPanel for rerun mutation
  const rawResult = analysis?.stage_results[`stage_${stage}`]
  const result = rawResult as Stage7Result | null | undefined

  if (isSkippedStage(rawResult)) {
    return (
      <div className="space-y-6">
        <StageHeader stage={7} name="Hub Gene Analysis" status={status?.status ?? 'pending'} elapsedSeconds={null} />
        <SkippedStageNotice />
      </div>
    )
  }

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

      <StageParamsPanel
        stage={7}
        analysisId={analysisId}
        currentParams={analysis?.parameters ?? null}
        canRerun={status?.mode === 'guided'}
      />

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

      {result.community_hubs && Object.keys(result.community_hubs).length > 0 && (
        <div className="space-y-4">
          <div>
            <h3 className="text-sm font-medium text-hf-fg1 font-sans">Community-Specific Hub Genes</h3>
            <p className="text-xs text-hf-fg3 font-sans mt-0.5">
              Centrality ranked within each Leiden module. Community hubs are more
              disease-specific than global hubs (Barabási et al. 2011, Nat Rev Genet 12:56–68).
            </p>
          </div>
          {Object.entries(result.community_hubs).map(([cidStr, hubs]) => {
            if (hubs.length === 0) return null
            const top5 = hubs.slice(0, 5) as CommunityHubRow[]
            return (
              <div key={cidStr} className="space-y-1">
                <p className="text-xs font-medium text-hf-fg2 font-sans">
                  Community {cidStr}
                  <span className="text-hf-fg3 font-normal ml-1">
                    ({hubs[0].community_size} genes)
                  </span>
                </p>
                <DataTable
                  data={top5}
                  columns={communityColumns}
                  filterPlaceholder={`Filter community ${cidStr} genes...`}
                  filterKeys={['gene_symbol']}
                />
              </div>
            )
          })}
        </div>
      )}

      <DataSources sources={SOURCES} />
    </div>
  )
}
