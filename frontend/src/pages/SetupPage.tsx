import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Input } from '@/components/ui/input'
import { Button } from '@/components/ui/button'
import { PlantSelector } from '@/components/setup/PlantSelector'
import { DiseaseSelector } from '@/components/setup/DiseaseSelector'
import { ModeToggle } from '@/components/setup/ModeToggle'
import { AdvancedParameters, DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'
import type { AdvancedParams } from '@/components/setup/AdvancedParameters'
import { useStartAnalysis } from '@/hooks/useStartAnalysis'
import { api } from '@/lib/api'
import { isTerminalStatus } from '@/types/api'

// ============================================================================
// Helpers
// ============================================================================

function generateDefaultName(): string {
  const date = new Date().toISOString().slice(0, 10) // 'YYYY-MM-DD'
  return `Analysis — ${date}`
}

/** Parse a textarea value into non-empty trimmed lines. */
function parseCompoundLines(raw: string): string[] {
  return raw
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

/** Parse a textarea value of gene symbols / UniProt accessions, one per line. */
function parseTargetLines(raw: string): string[] {
  return raw
    .split('\n')
    .map((l) => l.trim())
    .filter(Boolean)
}

// ============================================================================
// InputModeToggle — standard vs manual_compounds vs manual_targets
// ============================================================================

type InputMode = 'standard' | 'manual_compounds' | 'manual_targets'

interface InputModeToggleProps {
  value: InputMode
  onChange: (v: InputMode) => void
}

function InputModeToggle({ value, onChange }: InputModeToggleProps) {
  const base =
    'flex-1 py-1.5 px-3 rounded text-sm font-medium transition-colors focus:outline-none'
  const active = 'bg-hf-accent text-hf-bg'
  const inactive = 'text-hf-fg2 hover:text-hf-fg1'

  return (
    <div
      className="flex gap-1 bg-hf-bg border border-hf-border rounded-lg p-1"
      role="group"
      aria-label="Input mode"
    >
      <button
        type="button"
        className={`${base} ${value === 'standard' ? active : inactive}`}
        onClick={() => onChange('standard')}
        aria-pressed={value === 'standard'}
      >
        Standard (plant-based)
      </button>
      <button
        type="button"
        className={`${base} ${value === 'manual_compounds' ? active : inactive}`}
        onClick={() => onChange('manual_compounds')}
        aria-pressed={value === 'manual_compounds'}
        data-testid="input-mode-manual"
      >
        Manual compounds
      </button>
      <button
        type="button"
        className={`${base} ${value === 'manual_targets' ? active : inactive}`}
        onClick={() => onChange('manual_targets')}
        aria-pressed={value === 'manual_targets'}
        data-testid="input-mode-manual-targets"
      >
        Manual targets
      </button>
    </div>
  )
}

// ============================================================================
// SetupPage
// ============================================================================

export default function SetupPage() {
  const navigate = useNavigate()
  const mutation = useStartAnalysis()

  // Form state
  const [name, setName] = useState(() => generateDefaultName())
  const [plantIds, setPlantIds] = useState<string[]>([])
  const [diseaseIds, setDiseaseIds] = useState<string[]>([])
  const [mode, setMode] = useState<'guided' | 'auto'>('guided')
  const [params, setParams] = useState<AdvancedParams>(DEFAULT_PARAMS)
  const [inputMode, setInputMode] = useState<InputMode>('standard')
  const [compoundsRaw, setCompoundsRaw] = useState('')
  const [targetsRaw, setTargetsRaw] = useState('')

  const isManualCompounds = inputMode === 'manual_compounds'
  const isManualTargets = inputMode === 'manual_targets'
  const isManual = isManualCompounds || isManualTargets
  const parsedCompounds = isManualCompounds ? parseCompoundLines(compoundsRaw) : []
  const parsedTargets = isManualTargets ? parseTargetLines(targetsRaw) : []

  // Cache restore: if there's an in-progress analysis, redirect to it
  useEffect(() => {
    const lastId = localStorage.getItem('hf_last_analysis_id')
    if (!lastId) return
    api
      .getAnalysisStatus(lastId)
      .then((status) => {
        // Redirect for in-progress OR completed analyses; leave failed/rejected on setup page
        if (!isTerminalStatus(status.status) || status.status === 'complete') {
          navigate(`/analysis/${lastId}`, { replace: true })
        }
      })
      .catch(() => {
        // Analysis not found or network error — clear stale cache
        localStorage.removeItem('hf_last_analysis_id')
      })
  }, [navigate])

  // Derived validation
  const hasInput = isManualCompounds
    ? parsedCompounds.length > 0
    : isManualTargets
      ? parsedTargets.length > 0
      : plantIds.length > 0
  const isDisabled = !hasInput || diseaseIds.length === 0 || mutation.isPending

  function handleSubmit() {
    if (isDisabled) return

    const baseParams: Record<string, unknown> = {
      ...(params as unknown as Record<string, unknown>),
    }
    if (isManualCompounds) {
      baseParams['_input_mode'] = 'manual_compounds'
    } else if (isManualTargets) {
      baseParams['_input_mode'] = 'manual_targets'
    }

    mutation.mutate({
      request: {
        name,
        mode,
        plant_ids: isManual ? [] : plantIds,
        disease_ids: diseaseIds,
        parameters: baseParams,
      },
      compounds: isManualCompounds ? parsedCompounds : undefined,
      targets: isManualTargets ? parsedTargets : undefined,
    })
  }

  return (
    <div className="max-w-2xl mx-auto py-12 px-6">
      <h1 className="font-display text-3xl text-hf-fg1 mb-8">New Analysis</h1>

      {/* Analysis Name */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Analysis Name</p>
        <Input
          value={name}
          onChange={(e) => setName(e.target.value)}
          placeholder="Enter analysis name"
          className="border-hf-border bg-hf-surface text-hf-fg1"
        />
      </div>

      {/* Input Mode */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Input Mode</p>
        <InputModeToggle value={inputMode} onChange={setInputMode} />
        {isManualCompounds && (
          <p className="text-xs text-hf-fg3 mt-2">
            Stages 1–2 (compound selection and ADME screening) will be skipped.
            Compounds are validated via PubChem; invalid structures are discarded.
          </p>
        )}
        {isManualTargets && (
          <p className="text-xs text-hf-fg3 mt-2">
            Stages 1–3 (compound selection, ADME screening, and target identification) will be skipped.
            Targets are validated via UniProt (human proteome); unrecognised entries are discarded.
          </p>
        )}
      </div>

      {/* Plants — hidden in manual mode */}
      {!isManual && (
        <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4" data-testid="plants-section">
          <p className="text-sm font-medium text-hf-fg2 mb-2">Plants</p>
          <PlantSelector value={plantIds} onChange={setPlantIds} />
        </div>
      )}

      {/* Manual compound input */}
      {isManualCompounds && (
        <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4" data-testid="compounds-section">
          <p className="text-sm font-medium text-hf-fg2 mb-2">Compounds</p>
          <textarea
            value={compoundsRaw}
            onChange={(e) => setCompoundsRaw(e.target.value)}
            placeholder="Enter SMILES or InChI strings, one per line"
            rows={6}
            data-testid="compounds-textarea"
            className="w-full rounded-md border border-hf-border bg-hf-bg text-hf-fg1 text-sm p-3 placeholder:text-hf-fg3 focus:outline-none focus:ring-1 focus:ring-hf-accent resize-y font-mono"
          />
          {parsedCompounds.length > 0 && (
            <p className="text-xs text-hf-fg3 mt-1">
              {parsedCompounds.length} structure{parsedCompounds.length !== 1 ? 's' : ''} entered
            </p>
          )}
        </div>
      )}

      {/* Manual target input */}
      {isManualTargets && (
        <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4" data-testid="targets-section">
          <p className="text-sm font-medium text-hf-fg2 mb-2">Targets</p>
          <textarea
            value={targetsRaw}
            onChange={(e) => setTargetsRaw(e.target.value)}
            placeholder="Enter gene symbols or UniProt accessions, one per line"
            rows={6}
            data-testid="targets-textarea"
            className="w-full rounded-md border border-hf-border bg-hf-bg text-hf-fg1 text-sm p-3 placeholder:text-hf-fg3 focus:outline-none focus:ring-1 focus:ring-hf-accent resize-y font-mono"
          />
          {parsedTargets.length > 0 && (
            <p className="text-xs text-hf-fg3 mt-1">
              {parsedTargets.length} target{parsedTargets.length !== 1 ? 's' : ''} entered
            </p>
          )}
        </div>
      )}

      {/* Disease */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Diseases</p>
        <DiseaseSelector value={diseaseIds} onChange={setDiseaseIds} />
      </div>

      {/* Mode */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Mode</p>
        <ModeToggle value={mode} onChange={setMode} />
      </div>

      {/* Advanced Parameters */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Advanced Parameters</p>
        <AdvancedParameters value={params} onChange={setParams} />
      </div>

      {/* Error message */}
      {mutation.isError && (
        <div className="text-hf-danger text-sm mt-2">
          {mutation.error?.message}
        </div>
      )}

      {/* Submit */}
      <Button
        className="w-full mt-2"
        disabled={isDisabled}
        onClick={handleSubmit}
      >
        {mutation.isPending ? 'Starting...' : 'Start Analysis'}
      </Button>
    </div>
  )
}
