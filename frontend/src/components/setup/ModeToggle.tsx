import { cn } from '@/lib/utils'
import type { AnalysisMode } from '@/types/api'

interface ModeOption {
  value: AnalysisMode
  label: string
  description: string
}

const OPTIONS: ModeOption[] = [
  {
    value: 'guided',
    label: 'Guided',
    description: 'Manual approval at each stage',
  },
  {
    value: 'auto',
    label: 'Auto',
    description: 'Fully automatic',
  },
]

interface ModeToggleProps {
  value: AnalysisMode
  onChange: (mode: AnalysisMode) => void
}

export function ModeToggle({ value, onChange }: ModeToggleProps) {
  return (
    <div className="flex gap-2">
      {OPTIONS.map((option) => {
        const isActive = value === option.value
        return (
          <button
            key={option.value}
            type="button"
            onClick={() => onChange(option.value)}
            className={cn(
              'flex flex-1 flex-col items-start rounded-sm px-4 py-3 text-left transition-colors',
              isActive
                ? 'bg-hf-fg1 text-white'
                : 'bg-hf-surface border border-hf-border text-hf-fg2 hover:border-hf-border-strong'
            )}
          >
            <span className="text-sm font-medium">{option.label}</span>
            <span
              className={cn(
                'mt-0.5 text-xs',
                isActive ? 'text-white/70' : 'text-hf-fg3'
              )}
            >
              {option.description}
            </span>
          </button>
        )
      })}
    </div>
  )
}
