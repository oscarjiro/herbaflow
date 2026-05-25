import { useState } from 'react'
import { StageHeader } from '@/components/shared/StageHeader'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { StatusBadge } from '@/components/shared/StatusBadge'
import { EmptyState } from '@/components/shared/EmptyState'
import { DataSources } from '@/components/shared/DataSources'
import { cn } from '@/lib/utils'
import { StageParamsPanel } from '@/components/shared/StageParamsPanel'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage2Result, AdmeCompoundResult } from '@/types/api'

const SOURCES = [
  {
    name: 'PubChem Compound',
    url: 'https://pubchem.ncbi.nlm.nih.gov/',
    description: 'Physicochemical property data (MW, LogP, TPSA, HBD, HBA, rotatable bonds, NP-likeness) sourced from PubChem compound records computed via RDKit during ETL.',
    citation: 'Kim S et al. (2023). PubChem 2023 update. Nucleic Acids Res 51(D1):D1373–D1380.',
  },
  {
    name: 'RDKit',
    url: 'https://www.rdkit.org/',
    description: 'Open-source cheminformatics toolkit used to compute molecular descriptors (ADME properties) and PAINS pattern matching from SMILES strings.',
  },
]

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
    key: 'molecular_weight',
    header: 'MW (Da)',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(1) : '—',
  },
  {
    key: 'logp',
    header: 'LogP',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(2) : '—',
  },
  {
    key: 'tpsa',
    header: 'TPSA (Å²)',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(1) : '—',
  },
  {
    key: 'hbond_donors',
    header: 'HBD',
    sortable: true,
    render: (v) => v != null ? String(v) : '—',
  },
  {
    key: 'hbond_acceptors',
    header: 'HBA',
    sortable: true,
    render: (v) => v != null ? String(v) : '—',
  },
  {
    key: 'np_likeness_score',
    header: 'NP-likeness',
    sortable: true,
    render: (v) => v != null ? (v as number).toFixed(3) : '—',
  },
  {
    key: 'adme_pass',
    header: 'Result',
    render: (value, row) => {
      if (row.is_np_exception) {
        return <StatusBadge status="stage_1_awaiting_approval" label="Pass (NP)" />
      }
      return (
        <StatusBadge
          status={value ? 'complete' : 'failed'}
          label={value ? 'Pass' : 'Fail'}
        />
      )
    },
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
  {
    key: 'is_pains_positive',
    header: 'PAINS',
    render: (value) => (
      <StatusBadge
        status={value ? 'failed' : 'neutral'}
        label={value ? 'PAINS' : 'Clean'}
      />
    ),
  },
]

export function Stage2Panel({ stage, analysis, status, analysisId }: Stage2PanelProps) {
  const result = analysis?.stage_results[`stage_${stage}`] as Stage2Result | null | undefined
  const [filterMode, setFilterMode] = useState<FilterMode>('all')

  const total = result ? result.passed + result.failed + result.np_exceptions : 0
  const passedPct = total > 0 ? (((result?.passed ?? 0) / total) * 100).toFixed(1) : '0.0'
  const failedPct = total > 0 ? (((result?.failed ?? 0) / total) * 100).toFixed(1) : '0.0'

  const filteredCompounds: AdmeRow[] = result
    ? (filterMode === 'passed'
      ? result.compounds.filter(c => c.adme_pass || c.is_np_exception)
      : filterMode === 'failed'
        ? result.compounds.filter(c => !c.adme_pass && !c.is_np_exception)
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
          <StageParamsPanel
            stage={2}
            analysisId={analysisId}
            currentParams={analysis?.parameters ?? null}
            canRerun={status?.mode === 'guided'}
          />
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

          <div className="space-y-1 text-xs text-hf-fg3 font-sans">
            <p>
              <span className="font-medium text-hf-fg2">Filter criteria:</span> Lipinski RO5 (MW ≤ 500 Da, LogP ≤ 5, HBD ≤ 5, HBA ≤ 10) + Veber rules (TPSA ≤ 140 Å², rotatable bonds ≤ 10).
            </p>
            <p>
              <span className="font-medium text-hf-fg2">NP Exception:</span> Compounds failing Lipinski/Veber rules but with NP-likeness score ≥ threshold are passed through as natural product exceptions — natural products often violate Lipinski due to their structural complexity while retaining oral bioavailability.
            </p>
            <p>
              <span className="font-medium text-hf-fg2">PAINS:</span> Pan-Assay INterference compoundS — structural motifs known to produce false positives in biochemical assays. Flagged for awareness; not excluded from the pipeline.
            </p>
          </div>

          <DataSources sources={SOURCES} />
        </>
      )}
    </div>
  )
}
