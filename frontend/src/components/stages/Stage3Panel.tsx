import { useState, useCallback, useRef } from 'react'
import { useQueryClient } from '@tanstack/react-query'
import { StageHeader } from '@/components/shared/StageHeader'
import { StatCard } from '@/components/shared/StatCard'
import { DataTable } from '@/components/shared/DataTable'
import type { ColumnDef } from '@/components/shared/DataTable'
import { EmptyState } from '@/components/shared/EmptyState'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage2Result, Stage3Result, TargetResult, UncoveredCompound, STPTargetImport } from '@/types/api'
import { parseSTPCsv, generateSTPExportCsv } from '@/lib/stp'
import { api } from '@/lib/api'

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
  // Use Stage 2 compounds for total count when available.
  // If Stage 2 result not loaded, hide the X/Y line (coveredCount = null signals this).
  const totalCompounds = allCompounds.length
  const coveredCount = totalCompounds > 0 ? totalCompounds - uncoveredCompounds.length : null

  // Note: _analysisId (from props) is used in Task 6's import handler
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
    setTimeout(() => URL.revokeObjectURL(url), 100)
  }, [result])

  const queryClient = useQueryClient()
  const fileInputRef = useRef<HTMLInputElement>(null)

  // Import panel state
  const [selectedCompoundId, setSelectedCompoundId] = useState<string>('')
  const [rawCsvText, setRawCsvText] = useState<string>('')
  const [minProbability, setMinProbability] = useState<number>(0.1)
  const [parseError, setParseError] = useState<string | null>(null)
  const [parsedTargets, setParsedTargets] = useState<STPTargetImport[]>([])
  const [importing, setImporting] = useState(false)
  const [importResult, setImportResult] = useState<{ imported: number; skipped: number } | null>(null)

  const handleCsvChange = useCallback((text: string) => {
    setRawCsvText(text)
    setImportResult(null)
    if (!text.trim()) {
      setParsedTargets([])
      setParseError(null)
      return
    }
    const { targets, error } = parseSTPCsv(text, minProbability)
    setParsedTargets(targets)
    setParseError(error)
  }, [minProbability])

  const handleProbabilityChange = useCallback((prob: number) => {
    setMinProbability(prob)
    if (rawCsvText.trim()) {
      const { targets, error } = parseSTPCsv(rawCsvText, prob)
      setParsedTargets(targets)
      setParseError(error)
    }
  }, [rawCsvText])

  const handleFileUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (!file) return
    const reader = new FileReader()
    reader.onload = (ev) => {
      const text = ev.target?.result as string
      handleCsvChange(text)
    }
    reader.readAsText(file)
  }, [handleCsvChange])

  const handleImport = useCallback(async () => {
    if (!selectedCompoundId || parsedTargets.length === 0) return
    setImporting(true)
    try {
      const response = await api.importTargets(_analysisId, {
        compound_id: selectedCompoundId,
        targets: parsedTargets,
      })
      setImportResult(response)
      // Invalidate analysis query so Stage3Panel re-fetches updated stage_results
      await queryClient.invalidateQueries({ queryKey: ['analysis', _analysisId] })
      // Reset panel
      setRawCsvText('')
      setParsedTargets([])
      setSelectedCompoundId('')
      if (fileInputRef.current) fileInputRef.current.value = ''
    } catch (err) {
      setParseError(err instanceof Error ? err.message : 'Import failed')
    } finally {
      setImporting(false)
    }
  }, [selectedCompoundId, parsedTargets, _analysisId, queryClient])

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
                    {coveredCount !== null
                      ? <>{coveredCount} of {totalCompounds} compounds have targets · </>
                      : null}
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
                    {showImportPanel ? 'Hide Import Panel' : '↑ Import STP Results'}
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
                {showImportPanel ? 'Hide Import Panel' : '↑ Import STP Results'}
              </button>
            </div>
          )}

          {/* Import panel */}
          {showImportPanel && (
            <div className="rounded-md border border-hf-border bg-hf-bg2 p-4 space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-xs font-sans font-medium text-hf-fg2">Import STP Results</p>
                <button
                  onClick={() => setShowImportPanel(false)}
                  className="text-xs text-hf-fg3 hover:text-hf-fg1 font-sans"
                >
                  ✕
                </button>
              </div>

              {/* Step 1: Compound selector */}
              <div className="space-y-1">
                <label className="text-xs font-sans text-hf-fg3">
                  Importing targets for:
                </label>
                <select
                  value={selectedCompoundId}
                  onChange={e => setSelectedCompoundId(e.target.value)}
                  className="w-full text-xs font-sans bg-hf-bg1 border border-hf-border text-hf-fg2 rounded px-2 py-1.5 focus:outline-none focus:border-hf-fg3"
                >
                  <option value="">— Select compound —</option>
                  {allCompounds.map(c => {
                    const isUncovered = uncoveredCompounds.some(u => u.compound_id === c.compound_id)
                    return (
                      <option key={c.compound_id} value={c.compound_id}>
                        {c.canonical_name}{isUncovered ? ' — ⚠ 0 targets' : ''}
                      </option>
                    )
                  })}
                </select>
              </div>

              {/* Step 2: File upload + paste */}
              <div className="space-y-2">
                <label className="text-xs font-sans text-hf-fg3">
                  Upload or paste STP result CSV:
                </label>
                <div
                  className="border border-dashed border-hf-border rounded p-3 text-center cursor-pointer hover:border-hf-fg3 transition-colors"
                  onClick={() => fileInputRef.current?.click()}
                >
                  <p className="text-xs text-hf-fg3 font-sans">
                    Drop CSV file here or{' '}
                    <span className="underline underline-offset-2 text-hf-fg2">browse</span>
                  </p>
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv,.tsv,.txt"
                    className="hidden"
                    onChange={handleFileUpload}
                  />
                </div>
                <p className="text-xs text-hf-fg3 font-sans text-center">— or paste CSV text —</p>
                <textarea
                  value={rawCsvText}
                  onChange={e => handleCsvChange(e.target.value)}
                  placeholder={'Target,Uniprot,Common name,Gene name,...\nCarbonic anhydrase I,P00915,...'}
                  rows={4}
                  className="w-full text-xs font-mono bg-hf-bg1 border border-hf-border text-hf-fg2 rounded px-2 py-1.5 focus:outline-none focus:border-hf-fg3 resize-none"
                />
              </div>

              {/* Step 3: Probability threshold */}
              <div className="flex items-center gap-3">
                <label className="text-xs font-sans text-hf-fg3 shrink-0">
                  Min probability:
                </label>
                <input
                  type="range"
                  min={0}
                  max={1}
                  step={0.05}
                  value={minProbability}
                  onChange={e => handleProbabilityChange(parseFloat(e.target.value))}
                  className="flex-1"
                />
                <span className="text-xs font-mono text-hf-fg2 w-8 text-right">
                  {minProbability.toFixed(2)}
                </span>
              </div>

              {/* Parse error */}
              {parseError && (
                <p className="text-xs font-sans text-hf-terracotta">{parseError}</p>
              )}

              {/* Preview */}
              {parsedTargets.length > 0 && !parseError && (
                <div className="space-y-1">
                  <p className="text-xs font-sans text-hf-fg3">
                    Preview — {parsedTargets.length} targets will be imported:
                  </p>
                  <div className="max-h-32 overflow-y-auto border border-hf-border rounded">
                    <table className="w-full text-xs font-mono">
                      <thead className="bg-hf-bg1 sticky top-0">
                        <tr>
                          <th className="px-2 py-1 text-left text-hf-fg3 font-sans">Gene</th>
                          <th className="px-2 py-1 text-left text-hf-fg3 font-sans">UniProt</th>
                          <th className="px-2 py-1 text-right text-hf-fg3 font-sans">Prob.</th>
                        </tr>
                      </thead>
                      <tbody>
                        {parsedTargets.map((t, i) => (
                          <tr key={i} className="border-t border-hf-border">
                            <td className="px-2 py-0.5 text-hf-fg2">{t.gene_symbol}</td>
                            <td className="px-2 py-0.5 text-hf-fg3">{t.uniprot_id}</td>
                            <td className="px-2 py-0.5 text-hf-fg3 text-right">{t.probability.toFixed(2)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* Import result success message */}
              {importResult && (
                <p className="text-xs font-sans text-hf-fg2">
                  ✓ Imported {importResult.imported} targets
                  {importResult.skipped > 0 && ` · ${importResult.skipped} already existed`}
                </p>
              )}

              {/* Confirm button */}
              <button
                onClick={handleImport}
                disabled={!selectedCompoundId || parsedTargets.length === 0 || importing}
                className="w-full text-xs py-2 rounded border border-hf-border text-hf-fg2 hover:text-hf-fg1 hover:border-hf-fg3 transition-colors font-sans disabled:opacity-40 disabled:cursor-not-allowed"
              >
                {importing
                  ? 'Importing…'
                  : parsedTargets.length > 0
                  ? `Import ${parsedTargets.length} targets`
                  : 'Import STP Targets'}
              </button>
            </div>
          )}

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
