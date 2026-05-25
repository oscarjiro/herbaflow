import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { useResetFromStage } from '@/hooks/useResetFromStage'

// Stage → PipelineConfig key mapping
const STAGE_PARAM_KEY: Record<number, string> = {
  2: 'adme',
  3: 'target',
  4: 'disease_targets',
  6: 'ppi',
  7: 'hub_genes',
  8: 'enrichment',
}

// Default values (must match backend analysis/models.py exactly)
const PARAM_DEFAULTS: Record<string, Record<string, unknown>> = {
  adme: {
    max_mw: 500,
    max_logp: 5.0,
    max_hbd: 5,
    max_hba: 10,
    max_tpsa: 140.0,
    max_rotatable_bonds: 10,
    apply_veber: true,
    apply_pains: false,
    np_exception_threshold: 0.5,
  },
  target: {
    min_pchembl: 5.0,
    human_only: true,
    min_assay_confidence: 7,
  },
  disease_targets: {
    min_score: 0.3,
  },
  ppi: {
    min_confidence: 0.4,
  },
  hub_genes: {
    top_n: 20,
    use_hub_bottleneck: true,
  },
  enrichment: {
    fdr_threshold: 0.05,
    sources: ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG'],
  },
}

// Human-readable labels for each param field
const PARAM_LABELS: Record<string, Record<string, string>> = {
  adme: {
    max_mw: 'Max MW (Da)',
    max_logp: 'Max LogP',
    max_hbd: 'Max H-Bond Donors',
    max_hba: 'Max H-Bond Acceptors',
    max_tpsa: 'Max TPSA (Å²)',
    max_rotatable_bonds: 'Max Rotatable Bonds',
    apply_veber: 'Apply Veber Rules',
    apply_pains: 'Flag PAINS',
    np_exception_threshold: 'NP-likeness Threshold',
  },
  target: {
    min_pchembl: 'Min pChEMBL Value',
    human_only: 'Human Targets Only',
    min_assay_confidence: 'Min Assay Confidence (0–9)',
  },
  disease_targets: {
    min_score: 'Min Open Targets Score (0–1)',
  },
  ppi: {
    min_confidence: 'Min STRING Confidence (0–1)',
  },
  hub_genes: {
    top_n: 'Top N Hub Genes',
    use_hub_bottleneck: 'Hub+Bottleneck Composite',
  },
  enrichment: {
    fdr_threshold: 'FDR Threshold',
  },
}

// Numeric step values for inputs
const PARAM_STEP: Record<string, Record<string, number>> = {
  adme: {
    max_mw: 10,
    max_logp: 0.1,
    max_hbd: 1,
    max_hba: 1,
    max_tpsa: 5,
    max_rotatable_bonds: 1,
    np_exception_threshold: 0.05,
  },
  target: { min_pchembl: 0.5, min_assay_confidence: 1 },
  disease_targets: { min_score: 0.05 },
  ppi: { min_confidence: 0.05 },
  hub_genes: { top_n: 5 },
  enrichment: { fdr_threshold: 0.01 },
}

const ENRICHMENT_SOURCES = ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG']

interface StageParamsPanelProps {
  stage: number
  analysisId: string
  currentParams: Record<string, unknown> | null | undefined
  canRerun: boolean // guided mode && stage has results
}

export function StageParamsPanel({
  stage,
  analysisId,
  currentParams,
  canRerun,
}: StageParamsPanelProps) {
  const paramKey = STAGE_PARAM_KEY[stage]
  if (!paramKey) return null

  const defaults = PARAM_DEFAULTS[paramKey] ?? {}
  const labels = PARAM_LABELS[paramKey] ?? {}
  const steps = PARAM_STEP[paramKey] ?? {}

  const getEffectiveValues = () => ({
    ...defaults,
    ...((currentParams?.[paramKey] as Record<string, unknown>) ?? {}),
  })

  const [open, setOpen] = useState(false)
  const [values, setValues] = useState<Record<string, unknown>>(getEffectiveValues)
  const resetMutation = useResetFromStage(analysisId)

  // Sync when analysis.parameters change
  useEffect(() => {
    setValues(getEffectiveValues())
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentParams, paramKey])

  const handleRerun = () => {
    resetMutation.mutate({
      stage,
      body: { params: { [paramKey]: values }, rerun: true },
    })
  }

  return (
    <div className="rounded-lg border border-hf-border bg-hf-surface overflow-hidden">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-hf-fg2 hover:text-hf-fg1 transition-colors"
      >
        <span className="font-sans">Stage Parameters</span>
        {open ? (
          <ChevronDown className="h-4 w-4 text-hf-fg3" />
        ) : (
          <ChevronRight className="h-4 w-4 text-hf-fg3" />
        )}
      </button>

      {open && (
        <div className="border-t border-hf-border px-4 pb-4 pt-3 space-y-3">
          {/* Numeric and boolean params */}
          {Object.entries(defaults)
            .filter(([key]) => key !== 'sources')
            .map(([key, defaultVal]) => {
              const label = labels[key] ?? key
              const val = values[key]
              const isBoolean = typeof defaultVal === 'boolean'
              const step = steps[key] ?? 1

              if (isBoolean) {
                return (
                  <label
                    key={key}
                    className="flex items-center justify-between gap-3 cursor-pointer"
                  >
                    <span className="text-xs font-sans text-hf-fg2">{label}</span>
                    <input
                      type="checkbox"
                      checked={val as boolean}
                      onChange={(e) =>
                        setValues((v) => ({ ...v, [key]: e.target.checked }))
                      }
                      className="rounded border-hf-border accent-hf-fg1"
                    />
                  </label>
                )
              }

              return (
                <label key={key} className="flex items-center justify-between gap-3">
                  <span className="text-xs font-sans text-hf-fg2 flex-1">{label}</span>
                  <input
                    type="number"
                    value={val as number}
                    step={step}
                    onChange={(e) =>
                      setValues((v) => ({ ...v, [key]: Number(e.target.value) }))
                    }
                    className="w-24 rounded-sm border border-hf-border bg-hf-bg1 px-2 py-1 text-xs font-mono text-hf-fg1 focus:outline-none focus:ring-1 focus:ring-hf-border"
                  />
                </label>
              )
            })}

          {/* Enrichment sources multi-select (Stage 8 only) */}
          {paramKey === 'enrichment' && (
            <div className="space-y-1">
              <span className="text-xs font-sans text-hf-fg2">Pathway Sources</span>
              <div className="flex flex-wrap gap-2 mt-1">
                {ENRICHMENT_SOURCES.map((src) => {
                  const selected = (
                    (values.sources as string[] | undefined) ?? []
                  ).includes(src)
                  return (
                    <button
                      key={src}
                      type="button"
                      onClick={() => {
                        const current = Array.isArray(values.sources) ? (values.sources as string[]) : []
                        setValues((v) => ({
                          ...v,
                          sources: selected
                            ? current.filter((s) => s !== src)
                            : [...current, src],
                        }))
                      }}
                      className={`px-2 py-0.5 text-xs rounded-sm font-sans transition-colors border ${
                        selected
                          ? 'bg-hf-fg1 text-hf-bg border-hf-fg1'
                          : 'bg-hf-surface text-hf-fg2 border-hf-border hover:text-hf-fg1'
                      }`}
                    >
                      {src}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Rerun button (guided mode only) */}
          {canRerun && (
            <div className="pt-2 flex justify-end">
              <button
                type="button"
                disabled={resetMutation.isPending}
                onClick={handleRerun}
                aria-label={`Rerun stage ${stage} with updated parameters`}
                className="rounded-md bg-hf-fg1 px-3 py-1.5 text-xs font-medium text-hf-bg hover:opacity-90 disabled:opacity-50 transition-opacity font-sans"
              >
                {resetMutation.isPending ? 'Rerunning…' : `Rerun Stage ${stage}`}
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
