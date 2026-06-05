import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'
import { Button } from '@/components/ui/button'
import { SegmentedToggle } from '@/components/ui/segmented-toggle'
import { LineNumberedTextarea } from '@/components/ui/line-numbered-textarea'
import { PlantSelector } from '@/components/setup/PlantSelector'
import { DiseaseSelector } from '@/components/setup/DiseaseSelector'
import { ModeToggle } from '@/components/setup/ModeToggle'
import { AdvancedParameters, CheckboxField, DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'
import type { AdvancedParams } from '@/components/setup/AdvancedParameters'
import { ValidationReview } from '@/components/setup/ValidationReview'
import { useStartAnalysis } from '@/hooks/useStartAnalysis'
import { api } from '@/lib/api'
import type { ValidationPayload } from '@/lib/api'
import { isTerminalStatus } from '@/types/api'
import type { CreateAnalysisRequest } from '@/types/api'
import {
  validateSetupForm,
  nestAdvancedParams,
  manualFieldState,
  lineErrorsFor,
  SOFT_CAP_MANUAL_COMPOUNDS,
  HARD_CAP_MANUAL_COMPOUNDS,
  SOFT_CAP_MANUAL_TARGETS,
  HARD_CAP_MANUAL_TARGETS,
  SOFT_CAP_DISEASE_TARGETS,
  HARD_CAP_DISEASE_TARGETS,
  type SetupFormErrors,
} from '@/lib/schemas'

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
type ManualKind = 'compound' | 'target' | 'disease_target'
type ScopeName = 'compounds' | 'targets' | 'disease_targets'

/** A manual input scope to validate (and, after validation, review). */
interface ManualScope {
  kind: ManualKind
  scope: ScopeName
  label: string
  inputs: string[]
  lenient: boolean
}

/** A validated scope carried into the review step. */
interface ReviewScope {
  kind: ManualKind
  label: string
  total: number
  result: ValidationPayload
}

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
  /** Lenient target injection: keep unrecognized symbols flagged instead of dropped. Only applied for manual_targets mode. */
  lenient?: boolean
  /** Lenient disease-target resolution: keep unrecognized symbols flagged instead of dropped. Only applied for manual disease targets. */
  lenientDiseaseTargets?: boolean
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
    ...(a.inputMode === 'manual_targets' && a.lenient ? { skip_validation: true } : {}),
    ...(a.diseaseInputMode === 'manual_targets'
      ? { manual_disease_targets: a.parsedDiseaseTargets }
      : {}),
    ...(a.diseaseInputMode === 'manual_targets' && a.lenientDiseaseTargets
      ? { skip_disease_validation: true }
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
    // Coerce a null disease_id to '' in disease mode so the friendly
    // "Select a disease" min-length message fires instead of Zod's raw
    // "expected string, received null" type error.
    disease_id: a.diseaseInputMode === 'manual_targets' ? null : (a.diseaseId ?? ''),
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
  const [lenientTargets, setLenientTargets] = useState(false)
  const [diseaseInputMode, setDiseaseInputMode] = useState<DiseaseInputMode>('disease')
  const [diseaseTargetsRaw, setDiseaseTargetsRaw] = useState('')
  const [lenientDiseaseTargets, setLenientDiseaseTargets] = useState(false)
  // Validate-before-commit review state machine (manual modes only).
  const [reviewState, setReviewState] = useState<'idle' | 'validating' | 'reviewing'>('idle')
  const [reviewScopes, setReviewScopes] = useState<ReviewScope[] | null>(null)
  const [validatingKinds, setValidatingKinds] = useState<ManualKind[]>([])
  const [progress, setProgress] = useState<{ done: number; total: number }>({ done: 0, total: 0 })
  const [reviewError, setReviewError] = useState<string | null>(null)
  const parsedDiseaseTargets = diseaseInputMode === 'manual_targets' ? parseTargetLines(diseaseTargetsRaw) : []

  const isManualCompounds = inputMode === 'manual_compounds'
  const isManualTargets = inputMode === 'manual_targets'
  const parsedCompounds = isManualCompounds ? parseCompoundLines(compoundsRaw) : []
  const parsedTargets = isManualTargets ? parseTargetLines(targetsRaw) : []

  // Live cap state per manual field (count / soft warning / hard error).
  const compoundsCap = manualFieldState(parsedCompounds.length, SOFT_CAP_MANUAL_COMPOUNDS, HARD_CAP_MANUAL_COMPOUNDS, 'structure')
  const targetsCap = manualFieldState(parsedTargets.length, SOFT_CAP_MANUAL_TARGETS, HARD_CAP_MANUAL_TARGETS, 'target')
  const diseaseTargetsCap = manualFieldState(parsedDiseaseTargets.length, SOFT_CAP_DISEASE_TARGETS, HARD_CAP_DISEASE_TARGETS, 'target')

  // Live per-line format hints (client-side only; server dry-run is authoritative).
  const compoundsLineErrors = lineErrorsFor('compound', compoundsRaw.split('\n'))
  const targetsLineErrors = lineErrorsFor('target', targetsRaw.split('\n'))
  const diseaseTargetsLineErrors = lineErrorsFor('target', diseaseTargetsRaw.split('\n'))

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

  /**
   * Fire the create-analysis mutation from the current form state.
   *
   * `overrides` lets the review flow substitute the dry-run's resolved CANONICAL
   * KEYS (InChIKeys / UniProt accessions) for the raw typed inputs. Those keys are
   * DB cache hits at create time, so no PubChem/UniProt re-enrichment runs. The
   * standard (no-override) call path is unchanged.
   */
  function startCreate(overrides?: {
    compounds?: string[]
    targets?: string[]
    diseaseTargets?: string[]
  }) {
    mutation.mutate({
      request: buildCreateRequest({
        name,
        mode,
        plantIds,
        diseaseId,
        params,
        inputMode,
        diseaseInputMode,
        parsedCompounds: overrides?.compounds ?? parsedCompounds,
        parsedTargets: overrides?.targets ?? parsedTargets,
        parsedDiseaseTargets: overrides?.diseaseTargets ?? parsedDiseaseTargets,
        lenient: lenientTargets,
        lenientDiseaseTargets,
      }),
    })
  }

  /**
   * Every active manual input scope, in display order: the plant-side scope
   * (compounds XOR compound-targets) then the disease-side scope (disease targets).
   * Empty for a fully standard submit.
   */
  function activeManualInputs(): ManualScope[] {
    const out: ManualScope[] = []
    if (inputMode === 'manual_compounds') {
      out.push({ kind: 'compound', scope: 'compounds', label: 'Compounds', inputs: parsedCompounds, lenient: false })
    } else if (inputMode === 'manual_targets') {
      out.push({ kind: 'target', scope: 'targets', label: 'Compound targets', inputs: parsedTargets, lenient: lenientTargets })
    }
    if (diseaseInputMode === 'manual_targets') {
      out.push({ kind: 'disease_target', scope: 'disease_targets', label: 'Disease targets', inputs: parsedDiseaseTargets, lenient: lenientDiseaseTargets })
    }
    return out
  }

  function handleSubmit() {
    if (mutation.isPending || reviewState === 'validating') return

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
    setReviewError(null)

    // Standard mode submits directly — no dry-run. Manual modes get a review pass.
    const manuals = activeManualInputs()
    if (manuals.length === 0) {
      startCreate()
      return
    }

    const fail = (err: unknown) => {
      setReviewState('idle')
      setReviewScopes(null)
      setValidatingKinds([])
      setReviewError(err instanceof Error ? err.message : 'Validation failed — please try again.')
    }

    setReviewState('validating')
    setValidatingKinds(manuals.map((m) => m.kind))

    if (manuals.length === 1) {
      // Single scope keeps the chunked live-progress path.
      const m = manuals[0]
      setProgress({ done: 0, total: m.inputs.length })
      api
        .validateInChunks(m.kind, m.inputs, m.lenient, (done, total) => setProgress({ done, total }))
        .then((result) => {
          setReviewScopes([{ kind: m.kind, label: m.label, total: m.inputs.length, result }])
          setValidatingKinds([])
          setReviewState('reviewing')
        })
        .catch(fail)
      return
    }

    // Multiple scopes → one combined pass (shared target union, server-side).
    api
      .validateScopes(manuals.map((m) => ({ scope: m.scope, inputs: m.inputs, lenient: m.lenient })))
      .then((byScope) => {
        setReviewScopes(
          manuals.map((m) => ({
            kind: m.kind,
            label: m.label,
            total: m.inputs.length,
            result: byScope[m.scope],
          })),
        )
        setValidatingKinds([])
        setReviewState('reviewing')
      })
      .catch(fail)
  }

  /**
   * Extract the canonical keys the dry-run resolved+persisted, so create can reuse
   * them as DB cache hits (no re-enrichment):
   * - compound → InChIKey
   * - target / disease_target → UniProt accession, falling back to the gene symbol
   *   for unrecognized lenient inputs (`uniprot_id: null`).
   */
  function canonicalKeysFor(
    kind: 'compound' | 'target' | 'disease_target',
    valid: Record<string, unknown>[],
  ): string[] {
    if (kind === 'compound') {
      return valid.map((v) => v.inchikey as string).filter(Boolean)
    }
    return valid
      .map((v) => (v.uniprot_id as string) ?? (v.gene_symbol as string))
      .filter(Boolean)
  }

  function handleContinue() {
    // Reuse every reviewed scope's resolved canonical keys so create resolves them
    // as known-in-DB hits instead of re-calling providers.
    const override: { compounds?: string[]; targets?: string[]; diseaseTargets?: string[] } = {}
    for (const s of reviewScopes ?? []) {
      const keys = canonicalKeysFor(s.kind, s.result.valid)
      if (s.kind === 'compound') override.compounds = keys
      else if (s.kind === 'target') override.targets = keys
      else override.diseaseTargets = keys
    }
    setReviewState('idle')
    setReviewScopes(null)
    startCreate(override)
  }

  function handleBack() {
    setReviewState('idle')
    setReviewScopes(null)
  }

  /** Per-section progress note: a chunk count for a single scope, else a spinner label. */
  function validatingNote(kind: ManualKind): string | null {
    if (reviewState !== 'validating' || !validatingKinds.includes(kind)) return null
    return validatingKinds.length === 1 ? `${progress.done} / ${progress.total} validated…` : 'Validating…'
  }

  return (
    <div className="max-w-2xl mx-auto py-12 px-6">
      <h1 className="font-display text-3xl text-hf-fg1 mb-8">New Analysis</h1>

      {/* Plants */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Plants</p>
        <SegmentedToggle<InputMode>
          ariaLabel="Input mode"
          value={inputMode}
          onChange={(v) => { setInputMode(v); setFormErrors({}) }}
          options={[
            { value: 'standard', label: 'Standard (plant-based)' },
            { value: 'manual_compounds', label: 'Manual compounds', testId: 'input-mode-manual' },
            { value: 'manual_targets', label: 'Manual targets', testId: 'input-mode-manual-targets' },
          ]}
          className="mb-3"
        />

        {inputMode === 'standard' && (
          <p className="text-xs text-hf-fg3 mb-2">
            Select one or more plants from the KNApSAcK catalogue.
          </p>
        )}
        {isManualCompounds && (
          <p className="text-xs text-hf-fg3 mb-2">
            Paste compounds (Stages 1–2 skipped). One SMILES or InChI per line; mixed formats accepted.
          </p>
        )}
        {isManualTargets && (
          <p className="text-xs text-hf-fg3 mb-2">
            Paste compound targets (Stages 1–3 skipped). One gene symbol or UniProt accession per line; mixed formats accepted.
          </p>
        )}

        {inputMode === 'standard' ? (
          <div data-testid="plants-section">
            <PlantSelector value={plantIds} onChange={(v) => { setPlantIds(v); setFormErrors((prev) => ({ ...prev, plant_ids: undefined })) }} />
            {formErrors.plant_ids && (
              <p className="text-xs text-hf-danger mt-1">{formErrors.plant_ids}</p>
            )}
          </div>
        ) : isManualCompounds ? (
          <>
            <LineNumberedTextarea
              aria-label="Compounds"
              value={compoundsRaw}
              onChange={(v) => { setCompoundsRaw(v); setFormErrors((prev) => ({ ...prev, compounds: undefined })) }}
              placeholder={"CC(=O)Oc1ccccc1C(=O)O\nInChI=1S/C9H8O4/..."}
              error={formErrors.compounds ?? compoundsCap.error}
              warning={compoundsCap.warning}
              count={compoundsCap.count}
              lineErrors={compoundsLineErrors}
            />
            {validatingNote('compound') && (
              <p className="mt-2 text-xs text-hf-fg3" role="status" aria-live="polite">
                {validatingNote('compound')}
              </p>
            )}
            <div className="mt-2">
              <CheckboxField
                label="Apply ADME screening to these compounds"
                value={params.apply_adme_to_manual}
                onChange={(v) => setParams((p) => ({ ...p, apply_adme_to_manual: v }))}
              />
            </div>
          </>
        ) : (
          <>
            <LineNumberedTextarea
              aria-label="Targets"
              value={targetsRaw}
              onChange={(v) => { setTargetsRaw(v); setFormErrors((prev) => ({ ...prev, targets: undefined })) }}
              placeholder={"TP53\nBRCA1\nP04637"}
              error={formErrors.targets ?? targetsCap.error}
              warning={targetsCap.warning}
              count={targetsCap.count}
              lineErrors={targetsLineErrors}
            />
            {validatingNote('target') && (
              <p className="mt-2 text-xs text-hf-fg3" role="status" aria-live="polite">
                {validatingNote('target')}
              </p>
            )}
            <div className="mt-2">
              <CheckboxField
                label="Keep unrecognized symbols (lenient)"
                value={lenientTargets}
                onChange={setLenientTargets}
              />
              <p className="text-xs text-hf-fg3 mt-1">
                Unrecognized gene symbols are kept and flagged instead of dropped; UniProt accessions are still resolved.
              </p>
            </div>
          </>
        )}
      </div>

      {/* Disease */}
      <div className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4">
        <p className="text-sm font-medium text-hf-fg2 mb-2">Disease</p>
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
          <p className="text-xs text-hf-fg3 mb-2">
            Targets are sourced from Open Targets for the selected disease.
          </p>
        ) : (
          <p className="text-xs text-hf-fg3 mb-2">
            Paste disease targets (bypasses Open Targets). One gene symbol or UniProt accession per line; mixed formats accepted.
          </p>
        )}

        {diseaseInputMode === 'disease' ? (
          <>
            <DiseaseSelector value={diseaseId} onChange={(v) => { setDiseaseId(v); setFormErrors((prev) => ({ ...prev, disease_id: undefined })) }} />
            {formErrors.disease_id && (
              <p className="text-xs text-hf-danger mt-1">{formErrors.disease_id}</p>
            )}
          </>
        ) : (
          <>
            <LineNumberedTextarea
              aria-label="Disease targets"
              value={diseaseTargetsRaw}
              onChange={(v) => { setDiseaseTargetsRaw(v); setFormErrors((prev) => ({ ...prev, disease_targets: undefined })) }}
              placeholder={"TP53\nBRCA1\nP04637"}
              error={formErrors.disease_targets ?? diseaseTargetsCap.error}
              warning={diseaseTargetsCap.warning}
              count={diseaseTargetsCap.count}
              lineErrors={diseaseTargetsLineErrors}
            />
            {validatingNote('disease_target') && (
              <p className="mt-2 text-xs text-hf-fg3" role="status" aria-live="polite">
                {validatingNote('disease_target')}
              </p>
            )}
            <div className="mt-2">
              <CheckboxField
                label="Keep unrecognized symbols (lenient)"
                value={lenientDiseaseTargets}
                onChange={setLenientDiseaseTargets}
              />
              <p className="text-xs text-hf-fg3 mt-1">
                Unrecognized gene symbols are kept and flagged instead of dropped; UniProt accessions are still resolved.
              </p>
            </div>
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

      {/* Review */}
      {reviewState === 'reviewing' && reviewScopes && (
        <ValidationReview
          scopes={reviewScopes.map((s) => ({ label: s.label, total: s.total, result: s.result }))}
          onContinue={handleContinue}
          onBack={handleBack}
        />
      )}

      {/* Error message */}
      {(mutation.isError || reviewError) && (
        <div className="text-hf-danger text-sm mt-2">
          {reviewError ?? mutation.error?.message}
        </div>
      )}

      {/* Submit */}
      {reviewState !== 'reviewing' && (
        <Button
          className="w-full mt-2"
          disabled={isDisabled || reviewState === 'validating'}
          onClick={handleSubmit}
        >
          {reviewState === 'validating'
            ? 'Validating...'
            : mutation.isPending
              ? 'Starting...'
              : 'Start Analysis'}
        </Button>
      )}
    </div>
  )
}
