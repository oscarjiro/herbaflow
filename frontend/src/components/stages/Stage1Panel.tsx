import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { SkippedStageNotice } from '@/components/shared/SkippedStageNotice'
import { AddUserCompoundForm } from '@/components/shared/AddUserCompoundForm'
import { useRemoveUserCompound } from '@/hooks/useRemoveUserCompound'
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

export function Stage1Panel({ stage, analysis, status, analysisId }: Stage1PanelProps) {
  const rawResult = analysis?.stage_results[`stage_${stage}`]
  const result = rawResult as (Stage1Result & { user_modified?: boolean }) | null | undefined
  const removeCompound = useRemoveUserCompound(analysisId)

  const columns: ColumnDef<CompoundRow>[] = [
    {
      key: 'canonical_name',
      header: 'Compound Name',
      sortable: true,
      enableColumnFilter: true,
    },
    {
      key: 'plant_ids',
      header: 'Plants',
      sortable: true,
      render: (value) => (value as string[]).length,
    },
    {
      key: '_remove' as keyof CompoundRow,
      header: '',
      render: (_, row) => (
        <button
          onClick={() => removeCompound.mutate((row as CompoundRow).compound_id as string)}
          disabled={removeCompound.isPending}
          title="Remove compound from this analysis"
          className="text-xs text-hf-fg3 hover:text-hf-terracotta transition-colors disabled:opacity-40"
        >
          ✕
        </button>
      ),
    },
  ]

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

          {result.user_modified && (
            <p className="text-xs font-sans text-hf-fg3 italic">
              Compound list has been manually curated.
            </p>
          )}

          <DataTable
            data={result.compounds as CompoundRow[]}
            columns={columns}
            filterable
          />

          <div className="border-t border-hf-border pt-4">
            <h3 className="text-sm font-medium text-hf-fg2 mb-1">Curate Compound List</h3>
            <p className="text-xs text-hf-fg3 mb-3">
              Add compounds by SMILES or InChI string. Remove individual compounds using the ✕ button above.
            </p>
            <AddUserCompoundForm analysisId={analysisId} />
          </div>

          <DataSources sources={SOURCES} />
        </>
      )}
    </div>
  )
}
