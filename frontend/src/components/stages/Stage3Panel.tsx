import { useState, useCallback } from 'react'
import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { EmptyState } from '@/components/shared/EmptyState'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage2Result, Stage3Result, TargetResult, UncoveredCompound } from '@/types/api'
import { generateSTPExportCsv } from '@/lib/stp'

interface Stage3PanelProps {
  stage: number
  analysis: AnalysisRunResponse | undefined
  status: AnalysisStatusResponse | undefined
  analysisId: string
}

const GENE_PREVIEW_COUNT = 20

type TargetRow = TargetResult & Record<string, unknown>

const SOURCE_LABELS: Record<string, string> = {
  chembl: 'ChEMBL',
  pubchem_bioassay: 'PubChem BioAssay',
}

const SOURCE_CLASSES: Record<string, string> = {
  chembl: 'bg-hf-sage/20 text-hf-sage',
  pubchem_bioassay: 'bg-hf-terracotta/20 text-hf-terracotta',
}

const columns: ColumnDef<TargetRow>[] = [
  {
    key: 'gene_symbol',
    header: 'Gene Symbol',
    sortable: true,
    className: 'font-mono',
  },
  {
    key: 'compound_count',
    header: 'Binding Compounds',
    sortable: true,
  },
  {
    key: 'uniprot_id',
    header: 'UniProt ID',
    className: 'font-mono text-hf-fg3',
  },
  {
    key: 'source',
    header: 'Source',
    render: (value) => {
      const src = value as string
      return (
        <span className={`text-xs px-2 py-0.5 rounded font-mono ${SOURCE_CLASSES[src] ?? 'bg-hf-border text-hf-fg3'}`}>
          {SOURCE_LABELS[src] ?? src}
        </span>
      )
    },
  },
]

export function Stage3Panel({ stage, analysis, status, analysisId: _analysisId }: Stage3PanelProps) {
  const result = analysis?.stage_results[`stage_${stage}`] as Stage3Result | null | undefined
  const [showAllGenes, setShowAllGenes] = useState(false)

  const genes = result?.targets.map(t => t.gene_symbol) ?? []
  const visibleGenes = showAllGenes ? genes : genes.slice(0, GENE_PREVIEW_COUNT)

  // Stage 2 result contains all ADME-passed compounds (needed for import dropdown in Task 6)
  const stage2Result = analysis?.stage_results['stage_2'] as Stage2Result | null | undefined
  const allCompounds = stage2Result?.compounds ?? []

  const uncoveredCompounds: UncoveredCompound[] = result?.uncovered_compounds ?? []
  // totalCompounds = covered + uncovered
  const totalCompounds = allCompounds.length || (result ? uncoveredCompounds.length + (result.target_count > 0 ? 1 : 0) : 0)
  const coveredCount = totalCompounds - uncoveredCompounds.length

  const [showUncovered, setShowUncovered] = useState(false)
  // showImportPanel read in Task 6 (import panel rendering)
  const [showImportPanel, setShowImportPanel] = useState(false)

  const handleExportSTP = useCallback(() => {
    if (!result) return
    const csv = generateSTPExportCsv(result.uncovered_compounds)
    const blob = new Blob([csv], { type: 'text/csv' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'uncovered_compounds_stp.csv'
    a.click()
    URL.revokeObjectURL(url)
  }, [result])

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
            <StatCard label="Coverage" value={`${(result.coverage_pct ?? 0).toFixed(1)}%`} />
          </div>

          {/* Coverage section — Layout A: between stat cards and gene cloud */}
          {uncoveredCompounds.length > 0 && (
            <div className="rounded-md border border-hf-border bg-hf-bg2 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs font-sans font-medium text-hf-fg2">Coverage Details</p>
                  <p className="text-xs font-sans text-hf-fg3 mt-0.5">
                    {coveredCount} of {totalCompounds} compounds have targets ·{' '}
                    <span className="text-hf-fg2 font-medium">
                      {uncoveredCompounds.length} uncovered
                    </span>
                  </p>
                </div>
                <div className="flex gap-2">
                  <button
                    onClick={handleExportSTP}
                    className="text-xs px-3 py-1 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans"
                  >
                    ↓ Export SMILES for STP
                  </button>
                  <button
                    onClick={() => setShowImportPanel(prev => !prev)}
                    className="text-xs px-3 py-1 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans"
                  >
                    ↑ Import STP Results
                  </button>
                </div>
              </div>

              {/* Uncovered compounds list */}
              <div>
                <button
                  onClick={() => setShowUncovered(prev => !prev)}
                  className="text-xs text-hf-fg3 hover:text-hf-fg1 underline underline-offset-2 font-sans"
                >
                  {showUncovered ? 'Hide uncovered compounds' : `Show ${uncoveredCompounds.length} uncovered compounds`}
                </button>
                {showUncovered && (
                  <div className="flex flex-wrap gap-1.5 mt-2">
                    {uncoveredCompounds.map(c => (
                      <span
                        key={c.compound_id}
                        className="bg-hf-bg1 border border-hf-border text-hf-fg3 text-xs px-2 py-0.5 rounded font-mono"
                        title={c.smiles ?? 'No SMILES available'}
                      >
                        {c.canonical_name}
                        {!c.smiles && <span className="ml-1 text-hf-fg3 opacity-60">(no SMILES)</span>}
                      </span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          )}

          {/* All-covered state — show brief note and import button */}
          {uncoveredCompounds.length === 0 && result && (
            <div className="rounded-md border border-hf-border bg-hf-bg2 px-4 py-3 flex items-center justify-between">
              <p className="text-xs font-sans text-hf-fg3">
                All compounds covered ✓
              </p>
              <button
                onClick={() => setShowImportPanel(prev => !prev)}
                className="text-xs px-3 py-1 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans"
              >
                ↑ Import STP Results
              </button>
            </div>
          )}

          {/* Import panel placeholder — Task 6 renders content here when showImportPanel is true */}
          {showImportPanel && null}

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

          <p className="text-xs text-hf-fg3 font-sans">
            <span className="font-medium text-hf-fg2">Primary source:</span> ChEMBL (human protein targets, pChEMBL ≥ 5.0 = IC₅₀ ≤ 10µM). ·{' '}
            <span className="font-medium text-hf-fg2">Secondary source:</span> PubChem BioAssay — queried for compounds with zero ChEMBL targets; aggregates BindingDB, STITCH, and 300+ bioactivity sources (Kim et al. NAR 2023).
          </p>
        </>
      )}
    </div>
  )
}
