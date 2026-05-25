import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { SkippedStageNotice } from '@/components/shared/SkippedStageNotice'
import { isSkippedStage } from '@/types/api'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage1Result, CompoundResult } from '@/types/api'

const SOURCES = [
  {
    name: 'KNApSAcK Core',
    url: 'https://www.knapsackfamily.com/KNApSAcK/',
    description: 'Metabolite–species relationship database mapping plant-derived compounds to their source organisms. Provides compound canonical names, molecular identifiers, and plant species associations.',
  },
]

interface Stage1PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

type CompoundRow = CompoundResult & Record<string, unknown>

const columns: ColumnDef<CompoundRow>[] = [
  {
    key: 'canonical_name',
    header: 'Compound Name',
    sortable: true,
  },
  {
    key: 'plant_ids',
    header: 'Plants',
    sortable: true,
    render: (value) => (value as string[]).length,
  },
]

export function Stage1Panel({ stage, analysis, status }: Stage1PanelProps) {
  const rawResult = analysis?.stage_results[`stage_${stage}`]
  const result = rawResult as Stage1Result | null | undefined

  return (
    <div className="space-y-6">
      <StageHeader
        stage={1}
        name="Compound Selection"
        status={status?.status ?? 'complete'}
        elapsedSeconds={null}
      />

      {isSkippedStage(rawResult) ? (
        <SkippedStageNotice />
      ) : !result ? (
        <EmptyState message="Stage 1 results not yet available" />
      ) : (
        <>
          <div className="grid grid-cols-3 gap-4">
            <StatCard label="Total Compounds" value={result.total_compounds} />
            <StatCard label="Plants Covered" value={result.plants_covered} />
            <StatCard
              label="Avg Compounds / Plant"
              value={
                result.plants_covered > 0
                  ? (result.total_compounds / result.plants_covered).toFixed(1)
                  : '—'
              }
            />
          </div>

          <DataTable
            data={result.compounds as CompoundRow[]}
            columns={columns}
            filterPlaceholder="Filter compounds..."
            filterKeys={['canonical_name']}
          />

          <DataSources sources={SOURCES} />
        </>
      )}
    </div>
  )
}
