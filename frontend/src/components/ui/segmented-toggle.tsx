// segmented-toggle.tsx
import { cn } from '@/lib/utils'

export interface SegmentedOption<T extends string> {
  value: T
  label: string
  description?: string
  testId?: string
}

interface SegmentedToggleProps<T extends string> {
  options: SegmentedOption<T>[]
  value: T
  onChange: (value: T) => void
  ariaLabel: string
  className?: string
}

export function SegmentedToggle<T extends string>({
  options, value, onChange, ariaLabel, className,
}: SegmentedToggleProps<T>) {
  return (
    <div
      role="group"
      aria-label={ariaLabel}
      className={cn('flex gap-1 rounded-lg border border-hf-border bg-hf-bg p-1', className)}
    >
      {options.map((o) => {
        const active = o.value === value
        return (
          <button
            key={o.value}
            type="button"
            data-testid={o.testId}
            aria-pressed={active}
            onClick={() => onChange(o.value)}
            className={cn(
              'flex flex-1 flex-col items-start rounded px-3 py-1.5 text-left text-sm font-medium transition-colors focus:outline-none',
              active ? 'bg-hf-fg1 text-hf-bg' : 'text-hf-fg2 hover:text-hf-fg1',
            )}
          >
            <span>{o.label}</span>
            {o.description && (
              <span className={cn('mt-0.5 text-xs', active ? 'text-hf-bg/70' : 'text-hf-fg3')}>
                {o.description}
              </span>
            )}
          </button>
        )
      })}
    </div>
  )
}
