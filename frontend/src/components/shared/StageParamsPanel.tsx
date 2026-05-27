import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import { useResetFromStage } from '@/hooks/useResetFromStage'
import {
  STAGE_PARAM_KEY,
  PARAM_DEFAULTS,
  PARAM_LABELS,
  PARAM_STEP,
  PARAM_SELECT_OPTIONS,
  ENRICHMENT_SOURCES,
} from '@/lib/stage-params'

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
  const selectOptions = PARAM_SELECT_OPTIONS[paramKey] ?? {}

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
          <div className="text-xs text-hf-fg3 mb-2">
            Rerun Stage {stage} with updated parameters
          </div>
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

              const selectOpts = selectOptions[key]
              if (selectOpts) {
                return (
                  <label key={key} className="flex items-center justify-between gap-3">
                    <span className="text-xs font-sans text-hf-fg2 flex-1">{label}</span>
                    <select
                      value={val as number | string}
                      onChange={(e) =>
                        setValues((v) => ({ ...v, [key]: Number(e.target.value) }))
                      }
                      className="rounded-sm border border-hf-border bg-hf-bg1 px-2 py-1 text-xs font-sans text-hf-fg1 focus:outline-none focus:ring-1 focus:ring-hf-border"
                    >
                      {selectOpts.map((opt) => (
                        <option key={opt.value} value={opt.value}>
                          {opt.label}
                        </option>
                      ))}
                    </select>
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
