import { useState, useEffect, useRef } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { SegmentedToggle } from '@/components/ui/segmented-toggle'
import { PlantSelector } from '@/components/setup/PlantSelector'
import { DiseaseSelector } from '@/components/setup/DiseaseSelector'
import { ModeToggle } from '@/components/setup/ModeToggle'
import { AdvancedParameters, DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'
import type { AdvancedParams } from '@/components/setup/AdvancedParameters'
import { useStartAnalysis } from '@/hooks/useStartAnalysis'
import { api } from '@/lib/api'
import { isTerminalStatus } from '@/types/api'
import type { CreateAnalysisRequest } from '@/types/api'
import { validateSetupForm, nestAdvancedParams, type SetupFormErrors } from '@/lib/schemas'

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
// Types — standard vs manual_compounds vs manual_targets
// ============================================================================

type InputMode = 'standard' | 'manual_compounds' | 'manual_targets'
type DiseaseInputMode = 'disease' | 'manual_targets'

// ============================================================================
// Request builder
// ============================================================================

export interface BuildCreateArgs {
  name: string
  mode: 'guided' | 'auto'
  plantIds: string[]
  diseaseId: string | null
  params: AdvancedParams
  inputMode: 'standard' | 'manual_compounds' | 'manual_targets'
  diseaseInputMode: 'disease' | 'manual_targets'
  parsedCompounds: string[]
  parsedTargets: string[]
  parsedDiseaseTargets: string[]
}

/**
 * Build the create-analysis request from setup-form state.
 *
 * Pure: emits nested pipeline params plus inline manual inputs. Control keys
 * (`_input_mode`, `_disease_input_mode`, `_injected_disease_targets`) are NOT
 * sent — the server derives input/disease modes from the presence of the
 * top-level `compounds` / `targets` / `manual_disease_targets` fields.
 */
export function buildCreateRequest(a: BuildCreateArgs): CreateAnalysisRequest {
  const isManual = a.inputMode !== 'standard'
  return {
    name: a.name,
    mode: a.mode,
    plant_ids: isManual ? [] : a.plantIds,
    disease_id: a.diseaseInputMode === 'manual_targets' ? null : a.diseaseId,
    parameters: nestAdvancedParams(a.params),
    ...(a.inputMode === 'manual_compounds' ? { compounds: a.parsedCompounds } : {}),
    ...(a.inputMode === 'manual_targets' ? { targets: a.parsedTargets } : {}),
    ...(a.diseaseInputMode === 'manual_targets'
      ? { manual_disease_targets: a.parsedDiseaseTargets }
      : {}),
  }
}

export interface BuildSetupFormDataArgs {
  name: string
  mode: 'guided' | 'auto'
  inputMode: 'standard' | 'manual_compounds' | 'manual_targets'
  diseaseInputMode: 'disease' | 'manual_targets'
  plantIds: string[]
  diseaseId: string | null
  params: AdvancedParams
  parsedCompounds: string[]
  parsedTargets: string[]
  parsedDiseaseTargets: string[]
}

/**
 * Build the object handed to validateSetupForm.
 *
 * Parameters MUST be nested into the PipelineConfig shape the Zod schema (and the
 * server) expect — validating the flat accordion state directly fails every submit
 * with "Invalid input: expected object, received undefined" (the flat object has no
 * `adme`/`target`/… groups). This mirrors buildCreateRequest, which already nests.
 */
export function buildSetupFormData(a: BuildSetupFormDataArgs): Record<string, unknown> {
  const isManualCompounds = a.inputMode === 'manual_compounds'
  const isManualTargets = a.inputMode === 'manual_targets'
  return {
    name: a.name,
    mode: a.mode,
    disease_id: a.diseaseInputMode === 'manual_targets' ? null : a.diseaseId,
    parameters: nestAdvancedParams(a.params),
    ...(isManualCompounds
      ? { compounds: a.parsedCompounds }
      : isManualTargets
        ? { targets: a.parsedTargets }
        : { plant_ids: a.plantIds }),
    ...(a.diseaseInputMode === 'manual_targets'
      ? { disease_targets: a.parsedDiseaseTargets }
      : {}),
  }
}

// ============================================================================
// SetupPage
// ============================================================================

export default function SetupPage() {
  const navigate = useNavigate()
  const mutation = useStartAnalysis()

  // Form state
  const [name] = useState(() => generateDefaultName())
  const [plantIds, setPlantIds] = useState<string[]>([])
  const [diseaseId, setDiseaseId] = useState<string | null>(null)
  const [mode, setMode] = useState<'guided' | 'auto'>('guided')
  const [params, setParams] = useState<AdvancedParams>(DEFAULT_PARAMS)
  const [inputMode, setInputMode] = useState<InputMode>('standard')
  const [compoundsRaw, setCompoundsRaw] = useState('')
  const [targetsRaw, setTargetsRaw] = useState('')
  const [formErrors, setFormErrors] = useState<SetupFormErrors>({})
  // Disease input mode: select from DB or paste manual gene/accession list
  const [diseaseInputMode, setDiseaseInputMode] = useState<DiseaseInputMode>('disease')
  const [diseaseTargetsRaw, setDiseaseTargetsRaw] = useState('')
  const parsedDiseaseTargets = diseaseInputMode === 'manual_targets' ? parseTargetLines(diseaseTargetsRaw) : []

  // Refs for line-number scroll sync
  const compoundsTextareaRef = useRef<HTMLTextAreaElement>(null)
  const compoundsLineNumsRef = useRef<HTMLDivElement>(null)
  const targetsTextareaRef = useRef<HTMLTextAreaElement>(null)
  const targetsLineNumsRef = useRef<HTMLDivElement>(null)

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

  // Derived: only block submission while a request is in-flight;
  // field-level errors are surfaced by Zod on submit.
  const isDisabled = mutation.isPending

  function handleSubmit() {
    if (mutation.isPending) return

    // Run Zod validation against the same nested shape buildCreateRequest sends.
    const formData = buildSetupFormData({
      name,
      mode,
      inputMode,
      diseaseInputMode,
      plantIds,
      diseaseId,
      params,
      parsedCompounds,
      parsedTargets,
      parsedDiseaseTargets,
    })
    const { success, errors } = validateSetupForm(inputMode, diseaseInputMode, formData)
    if (!success) {
      setFormErrors(errors)
      return
    }
    setFormErrors({})

    mutation.mutate({
      request: buildCreateRequest({
        name,
        mode,
        plantIds,
        diseaseId,
        params,
        inputMode,
        diseaseInputMode,
        parsedCompounds,
        parsedTargets,
        parsedDiseaseTargets,
      }),
    })
  }

  return (
    <div className="max-w-2xl mx-auto py-12 px-6">
      <h1 className="font-display text-3xl text-hf-fg1 mb-8">New Analysis</h1>

      {/* Input Mode */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Input Mode</p>
        <SegmentedToggle<InputMode>
          ariaLabel="Input mode"
          value={inputMode}
          onChange={(v) => { setInputMode(v); setDiseaseInputMode('disease'); setFormErrors({}) }}
          options={[
            { value: 'standard', label: 'Standard (plant-based)' },
            { value: 'manual_compounds', label: 'Manual compounds', testId: 'input-mode-manual' },
            { value: 'manual_targets', label: 'Manual targets', testId: 'input-mode-manual-targets' },
          ]}
        />
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
          <PlantSelector value={plantIds} onChange={(v) => { setPlantIds(v); setFormErrors((prev) => ({ ...prev, plant_ids: undefined })) }} />
          {formErrors.plant_ids && (
            <p className="text-xs text-hf-danger mt-1">{formErrors.plant_ids}</p>
          )}
        </div>
      )}

      {/* Manual compound input */}
      {isManualCompounds && (
        <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4" data-testid="compounds-section">
          <p className="text-sm font-medium text-hf-fg2 mb-2">Compounds</p>
          <p className="text-xs text-hf-fg3 mb-2">One SMILES or InChI string per line. Mixed formats accepted.</p>
          <div className={`relative flex font-mono text-sm rounded-md border bg-hf-bg${formErrors.compounds ? ' border-hf-danger' : ' border-hf-border'}`}>
            {/* Line numbers */}
            <div
              ref={compoundsLineNumsRef}
              data-testid="compounds-line-nums"
              className="select-none pr-3 pl-3 text-hf-fg3 text-right min-w-[2.5rem] pt-3 leading-none overflow-hidden"
            >
              {(compoundsRaw === '' ? [] : compoundsRaw.split('\n')).map((_, i) => (
                <div key={`line-${i}`} className="leading-6">{i + 1}</div>
              ))}
            </div>
            <textarea
              ref={compoundsTextareaRef}
              value={compoundsRaw}
              onChange={(e) => { setCompoundsRaw(e.target.value); setFormErrors((prev) => ({ ...prev, compounds: undefined })) }}
              onScroll={() => {
                if (compoundsTextareaRef.current && compoundsLineNumsRef.current) {
                  compoundsLineNumsRef.current.scrollTop = compoundsTextareaRef.current.scrollTop
                }
              }}
              rows={6}
              data-testid="compounds-textarea"
              className="flex-1 rounded-r-md bg-hf-bg text-hf-fg1 text-sm p-3 pt-3 leading-6 placeholder:text-hf-fg3 focus:outline-none focus:ring-1 focus:ring-hf-accent resize-y border-0"
              placeholder={"CC(=O)Oc1ccccc1C(=O)O\nInChI=1S/C9H8O4/..."}
            />
          </div>
          {formErrors.compounds ? (
            <p className="text-xs text-hf-danger mt-1">{formErrors.compounds}</p>
          ) : parsedCompounds.length > 0 ? (
            <p className="text-xs text-hf-fg3 mt-1">
              {parsedCompounds.length} structure{parsedCompounds.length !== 1 ? 's' : ''} entered
            </p>
          ) : null}
        </div>
      )}

      {/* Manual target input */}
      {isManualTargets && (
        <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4" data-testid="targets-section">
          <p className="text-sm font-medium text-hf-fg2 mb-2">Targets</p>
          <p className="text-xs text-hf-fg3 mb-2">One gene symbol or UniProt accession per line.</p>
          <div className={`relative flex font-mono text-sm rounded-md border bg-hf-bg${formErrors.targets ? ' border-hf-danger' : ' border-hf-border'}`}>
            {/* Line numbers */}
            <div
              ref={targetsLineNumsRef}
              data-testid="targets-line-nums"
              className="select-none pr-3 pl-3 text-hf-fg3 text-right min-w-[2.5rem] pt-3 leading-none overflow-hidden"
            >
              {(targetsRaw === '' ? [] : targetsRaw.split('\n')).map((_, i) => (
                <div key={`line-${i}`} className="leading-6">{i + 1}</div>
              ))}
            </div>
            <textarea
              ref={targetsTextareaRef}
              value={targetsRaw}
              onChange={(e) => { setTargetsRaw(e.target.value); setFormErrors((prev) => ({ ...prev, targets: undefined })) }}
              onScroll={() => {
                if (targetsTextareaRef.current && targetsLineNumsRef.current) {
                  targetsLineNumsRef.current.scrollTop = targetsTextareaRef.current.scrollTop
                }
              }}
              rows={6}
              data-testid="targets-textarea"
              className="flex-1 rounded-r-md bg-hf-bg text-hf-fg1 text-sm p-3 pt-3 leading-6 placeholder:text-hf-fg3 focus:outline-none focus:ring-1 focus:ring-hf-accent resize-y border-0"
              placeholder={"TP53\nBRCA1\nP04637"}
            />
          </div>
          {formErrors.targets ? (
            <p className="text-xs text-hf-danger mt-1">{formErrors.targets}</p>
          ) : parsedTargets.length > 0 ? (
            <p className="text-xs text-hf-fg3 mt-1">
              {parsedTargets.length} target{parsedTargets.length !== 1 ? 's' : ''} entered
            </p>
          ) : null}
        </div>
      )}

      {/* Disease */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Disease Targets</p>
        {/* Disease input mode toggle */}
        <SegmentedToggle<DiseaseInputMode>
          ariaLabel="Disease input mode"
          value={diseaseInputMode}
          onChange={(v) => { setDiseaseInputMode(v); setFormErrors((prev) => ({ ...prev, disease_id: undefined, disease_targets: undefined })) }}
          options={[
            { value: 'disease', label: 'Select Disease' },
            { value: 'manual_targets', label: 'Manual Targets', testId: 'disease-input-mode-manual' },
          ]}
          className="mb-3"
        />

        {diseaseInputMode === 'disease' ? (
          <>
            <DiseaseSelector value={diseaseId} onChange={(v) => { setDiseaseId(v); setFormErrors((prev) => ({ ...prev, disease_id: undefined })) }} />
            {formErrors.disease_id && (
              <p className="text-xs text-hf-danger mt-1">{formErrors.disease_id}</p>
            )}
          </>
        ) : (
          <>
            <p className="text-xs text-hf-fg3 mb-2">
              One gene symbol or UniProt accession per line. Bypasses Open Targets.
            </p>
            <textarea
              value={diseaseTargetsRaw}
              onChange={(e) => { setDiseaseTargetsRaw(e.target.value); setFormErrors((prev) => ({ ...prev, disease_targets: undefined })) }}
              placeholder={"TP53\nBRCA1\nP04637"}
              rows={6}
              data-testid="disease-targets-textarea"
              className="w-full rounded-md border bg-hf-bg text-hf-fg1 text-sm p-3 font-mono placeholder:text-hf-fg3 focus:outline-none focus:ring-1 focus:ring-hf-accent resize-y border-hf-border"
            />
            {formErrors.disease_targets ? (
              <p className="text-xs text-hf-danger mt-1">{formErrors.disease_targets}</p>
            ) : parsedDiseaseTargets.length > 0 ? (
              <p className="text-xs text-hf-fg3 mt-1">
                {parsedDiseaseTargets.length} target{parsedDiseaseTargets.length !== 1 ? 's' : ''} entered
              </p>
            ) : null}
          </>
        )}
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
        {formErrors.parameters && (
          <p className="text-xs text-hf-danger mt-1">{formErrors.parameters}</p>
        )}
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
