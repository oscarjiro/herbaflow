import { useState } from 'react'
import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { EmptyState } from '@/components/shared/EmptyState'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage3Result, TargetResult } from '@/types/api'

interface Stage3PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

const GENE_PREVIEW_COUNT = 20

type TargetRow = TargetResult & Record<string, unknown>

const columns: ColumnDef<TargetRow>[] = [
  {
    key: 'gene_symbol',
    header: 'Gene Symbol',
    sortable: true,
    className: 'font-mono',
  },
  {
    key: 'compound_count',
    header: 'Compound Count',
    sortable: true,
  },
  {
    key: 'uniprot_id',
    header: 'UniProt ID',
    className: 'font-mono text-hf-fg3',
  },
]

export function Stage3Panel({ stage, analysis, status }: Stage3PanelProps) {
  const result = analysis?.stage_results[`stage_${stage}`] as Stage3Result | null | undefined
  const [showAllGenes, setShowAllGenes] = useState(false)

  const genes = result?.targets.map(t => t.gene_symbol) ?? []
  const visibleGenes = showAllGenes ? genes : genes.slice(0, GENE_PREVIEW_COUNT)

  return (
    <div className="space-y-6">
      <StageHeader
        stage={3}
        name="Target Identification"
        status={status?.status ?? 'complete'}
        elapsedSeconds={null}
      />

      {!result ? (
        <EmptyState message="Stage 3 results not yet available" />
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4">
            <StatCard label="Targets Found" value={result.target_count} />
            <StatCard label="Coverage" value={`${result.coverage_percent.toFixed(1)}%`} />
          </div>

          <div>
            <p className="text-xs font-sans text-hf-fg3 mb-2">Gene Targets</p>
            <div className="flex flex-wrap gap-1.5">
              {visibleGenes.map(gene => (
                <span
                  key={gene}
                  className="bg-hf-border text-hf-fg2 text-xs px-2 py-0.5 rounded font-mono"
                >
                  {gene}
                </span>
              ))}
            </div>
            {genes.length > GENE_PREVIEW_COUNT && (
              <button
                onClick={() => setShowAllGenes(prev => !prev)}
                className="mt-2 text-xs text-hf-fg3 hover:text-hf-fg1 underline underline-offset-2"
              >
                {showAllGenes
                  ? 'Show fewer genes'
                  : `Show all ${genes.length} genes`}
              </button>
            )}
          </div>

          <DataTable
            data={result.targets as TargetRow[]}
            columns={columns}
            filterPlaceholder="Filter targets..."
            filterKeys={['gene_symbol']}
          />
        </>
      )}
    </div>
  )
}
