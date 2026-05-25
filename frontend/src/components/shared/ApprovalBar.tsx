import { useState, useEffect } from 'react'
import { ChevronDown, ChevronRight, Settings } from 'lucide-react'
import {
  STAGE_PARAM_KEY,
  PARAM_DEFAULTS,
  PARAM_LABELS,
  PARAM_STEP,
  ENRICHMENT_SOURCES,
} from '@/lib/stage-params'

interface ApprovalBarProps {
  onApprove: (paramOverrides?: Record<string, unknown>) => void
  onReject: () => void
  isLoading?: boolean
  /** The stage that will run after approval (current_stage + 1). */
  nextStage?: number
  /** analysis.parameters from the current run — used to show stored defaults. */
  currentParams?: Record<string, unknown> | null
}

export function ApprovalBar({
  onApprove,
  onReject,
  isLoading,
  nextStage,
  currentParams,
}: ApprovalBarProps) {
  const paramKey = nextStage != null ? STAGE_PARAM_KEY[nextStage] : undefined
  const defaults = paramKey ? (PARAM_DEFAULTS[paramKey] ?? {}) : {}
  const labels = paramKey ? (PARAM_LABELS[paramKey] ?? {}) : {}
  const steps = paramKey ? (PARAM_STEP[paramKey] ?? {}) : {}

  const hasConfigurableParams = Boolean(paramKey && Object.keys(defaults).length > 0)

  const getEffectiveValues = (): Record<string, unknown> => ({
    ...defaults,
    ...((paramKey && (currentParams?.[paramKey] as Record<string, unknown>)) ?? {}),
  })

  const [open, setOpen] = useState(false)
  const [values, setValues] = useState<Record<string, unknown>>(getEffectiveValues)
  // Track whether user opened the panel; if so, send params with approval
  const [hasOpened, setHasOpened] = useState(false)

  // Reset when next stage changes (e.g. after a redo)
  useEffect(() => {
    setValues(getEffectiveValues())
    setOpen(false)
    setHasOpened(false)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nextStage, currentParams])

  const handleToggle = () => {
    if (!open) setHasOpened(true)
    setOpen((o) => !o)
  }

  const handleApprove = () => {
    if (hasOpened && paramKey) {
      onApprove({ [paramKey]: values })
    } else {
      onApprove(undefined)
    }
  }

  return (
    <div className="mt-8 border-t border-hf-border pt-6 space-y-4">
      {/* Configure Next Stage — only shown when next stage has configurable params */}
      {hasConfigurableParams && nextStage != null && (
        <div className="rounded-lg border border-hf-border bg-hf-surface overflow-hidden">
          <button
            type="button"
            onClick={handleToggle}
            className="w-full flex items-center justify-between px-4 py-3 text-sm font-medium text-hf-fg2 hover:text-hf-fg1 transition-colors"
          >
            <span className="flex items-center gap-2 font-sans">
              <Settings className="h-3.5 w-3.5" />
              Configure Stage {nextStage} Parameters
            </span>
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
                            const current = Array.isArray(values.sources)
                              ? (values.sources as string[])
                              : []
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
            </div>
          )}
        </div>
      )}

      {/* Action buttons */}
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={handleApprove}
          disabled={isLoading}
          className="rounded-sm bg-hf-fg1 px-5 py-2 text-sm font-medium text-white hover:opacity-90 disabled:opacity-45"
        >
          Approve & Continue
        </button>
        <button
          type="button"
          onClick={onReject}
          disabled={isLoading}
          className="rounded-sm border border-hf-border px-5 py-2 text-sm font-medium text-hf-fg2 hover:bg-hf-surface-2 disabled:opacity-45"
        >
          Reject
        </button>
      </div>
    </div>
  )
}
