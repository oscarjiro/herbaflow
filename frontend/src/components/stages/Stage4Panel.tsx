import { useState } from 'react'
import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { SkippedStageNotice } from '@/components/shared/SkippedStageNotice'
import { isSkippedStage } from '@/types/api'
import { StageParamsPanel } from '@/components/shared/StageParamsPanel'
import { AddTargetForm } from '@/components/shared/AddTargetForm'
import { useAddUserDiseaseTarget } from '@/hooks/useAddUserDiseaseTarget'
import { useRemoveUserDiseaseTarget } from '@/hooks/useRemoveUserDiseaseTarget'
import { useResetFromStage } from '@/hooks/useResetFromStage'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage4Result, DiseaseTargetResult } from '@/types/api'
import { ExternalLink } from '@/components/shared/ExternalLink'
import { sourceUrls } from '@/lib/sourceUrls'

const SOURCES = [
  {
    name: 'Open Targets Platform',
    url: 'https://platform.opentargets.org/',
    description: 'Disease–gene association scores (0–1) integrating genetic, genomic, and literature evidence via harmonic sum across evidence types. Pre-fetched to DB cache for reproducibility; falls back to live API when cache is empty.',
    citation: 'Ochoa D et al. (2021). Open Targets Platform: supporting systematic drug–target identification and prioritisation. Nucleic Acids Res 49:D1302–D1310.',
  },
]

interface Stage4PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

type DiseaseRow = DiseaseTargetResult & Record<string, unknown>

export function Stage4Panel({ stage, analysis, status, analysisId }: Stage4PanelProps) {
  const rawResult = analysis?.stage_results[`stage_${stage}`]
  const result = rawResult as Stage4Result | null | undefined
  const [showAddForm, setShowAddForm] = useState(false)
  const [addError, setAddError] = useState<string | null>(null)

  const addTarget = useAddUserDiseaseTarget(analysisId)
  const removeTarget = useRemoveUserDiseaseTarget(analysisId)
  const resetFromStage = useResetFromStage(analysisId)

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
      render: (value) => {
        const accession = value as string | null | undefined
        if (!accession) return <span className="text-hf-fg4">—</span>
        return (
          <ExternalLink
            href={sourceUrls.target(accession)}
            className="font-mono text-xs"
          >
            {accession}
          </ExternalLink>
        )
      },
    },
    {
      key: 'association_score',
      header: 'Open Targets Score',
      sortable: true,
      render: (value) =>
        value != null ? (value as number).toFixed(3) : '—',
    },
    {
      key: 'diseases',
      header: 'Disease(s)',
      render: (value, row) => {
        const diseases = (value as DiseaseTargetResult['diseases']) ?? []
        if (diseases.length > 1) {
          return (
            <div className="flex flex-wrap gap-1">
              {diseases.map((d) => (
                <span
                  key={d.disease_id}
                  className="inline-block px-1.5 py-0.5 rounded text-xs bg-hf-surface-2 border border-hf-border text-hf-fg2 font-sans"
                  title={`Score: ${d.association_score.toFixed(3)}`}
                >
                  {d.disease_name}
                </span>
              ))}
            </div>
          )
        }
        // Single disease or legacy (no diseases list) — fall back to disease_name
        return <span className="text-sm text-hf-fg1">{(row as DiseaseRow).disease_name as string}</span>
      },
    },
    {
      key: 'source',
      header: 'Source',
      render: (value) => {
        if (value === 'user_provided') {
          return <span className="text-xs px-2 py-0.5 rounded font-mono bg-hf-border text-hf-fg2">User</span>
        }
        const label = value === 'db_cache' ? 'Cached' : value === 'open_targets_api' ? 'Live API' : String(value)
        const badgeStatus = value === 'db_cache' ? 'complete' : 'stage_1_awaiting_approval'
        return <StatusBadge status={badgeStatus} label={label} />
      },
    },
    {
      key: '_remove' as keyof DiseaseRow,
      header: '',
      render: (_, row) => (
        <button
          onClick={() => removeTarget.mutate((row as DiseaseRow).gene_symbol as string)}
          disabled={removeTarget.isPending}
          title="Remove target from this analysis"
          className="text-xs text-hf-fg3 hover:text-hf-terracotta transition-colors disabled:opacity-40"
        >
          ✕
        </button>
      ),
    },
  ]

  const handleAddTarget = async (input: string) => {
    setAddError(null)
    const isAccession = /^[A-Z][0-9][A-Z0-9]{3}[0-9]$/i.test(input.trim())
    try {
      await addTarget.mutateAsync(
        isAccession ? { uniprot_id: input.trim() } : { gene_symbol: input.trim() }
      )
      setShowAddForm(false)
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to add target')
    }
  }

  return (
    <div className="space-y-6">
      <StageHeader
        stage={4}
        name="Disease Targets"
        status={status?.status ?? 'complete'}
        elapsedSeconds={null}
      />

      {isSkippedStage(rawResult) ? (
        <SkippedStageNotice />
      ) : !result ? (
        <EmptyState message="Stage 4 results not yet available" />
      ) : (
        <>
          <StageParamsPanel
            stage={4}
            analysisId={analysisId}
            currentParams={analysis?.parameters ?? null}
            canRerun={status?.mode === 'guided'}
          />

          {/* Stale banner */}
          {result.user_modified && (
            <div className="rounded-md border border-hf-border bg-hf-bg2 px-4 py-3 flex items-center justify-between">
              <p className="text-xs font-sans text-hf-fg2">
                ⚠ Stage 4 was modified — downstream results (Stages 5–8) are stale.
              </p>
              <button
                onClick={() => resetFromStage.mutate({ stage: 5, body: { rerun: true } })}
                disabled={resetFromStage.isPending}
                className="text-xs px-3 py-1 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans disabled:opacity-40"
              >
                {resetFromStage.isPending ? 'Starting…' : 'Rerun Stages 5–8'}
              </button>
            </div>
          )}

          <div className="grid grid-cols-1 gap-4 max-w-xs">
            <StatCard label="Disease-Associated Targets" value={result.disease_target_count} />
          </div>

          <div className="flex items-center justify-between">
            <span />
            <button
              onClick={() => { setShowAddForm(prev => !prev); setAddError(null) }}
              className="text-xs px-2 py-0.5 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans"
            >
              {showAddForm ? 'Cancel' : '＋ Add Target'}
            </button>
          </div>

          {showAddForm && (
            <AddTargetForm
              onSubmit={handleAddTarget}
              loading={addTarget.isPending}
              error={addError}
            />
          )}

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
              <span className="font-medium text-hf-fg2">Source:</span> <code className="text-hf-fg2">DB cache</code> = pre-fetched Open Targets data (ensures reproducibility); <code className="text-hf-fg2">API</code> = live Open Targets query at analysis time; <code className="text-hf-fg2">User</code> = manually added (score set to 1.0).
            </p>
          </div>

          <DataSources sources={SOURCES} />
        </>
      )}
    </div>
  )
}
