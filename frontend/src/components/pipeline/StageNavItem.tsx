import { Check, X } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface StageNavItemProps {
  stageNumber: number
  name: string
  status: 'completed' | 'running' | 'awaiting_approval' | 'future' | 'pending' | 'failed' | 'skipped'
  isActive: boolean
  onClick?: () => void
}

export function StageNavItem({
  stageNumber,
  name,
  status,
  isActive,
  onClick,
}: StageNavItemProps) {
  const isClickable =
    status === 'completed' || status === 'running' || status === 'awaiting_approval' || status === 'failed'
  // skipped stages are never clickable (handled separately from isClickable)

  function handleClick() {
    if (isClickable && onClick) onClick()
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={!isClickable}
      className={cn(
        'flex items-center gap-3 px-4 py-2.5 w-full text-left text-sm transition-colors',
        // Active background
        isActive && 'bg-hf-surface-2',
        // Left border highlight
        status === 'running' && 'border-l-2 border-hf-sage',
        status === 'awaiting_approval' && 'border-l-2 border-hf-warning',
        status === 'failed' && 'border-l-2 border-hf-danger',
        // Cursor
        isClickable ? 'cursor-pointer hover:bg-hf-surface-2' : 'cursor-default',
      )}
    >
      {/* Stage number */}
      <span className="text-xs text-hf-fg4 w-4 shrink-0 text-right">{stageNumber}</span>

      {/* Status icon */}
      {status === 'completed' && (
        <Check className="w-3.5 h-3.5 text-hf-success shrink-0" />
      )}
      {status === 'running' && (
        <div className="w-3.5 h-3.5 rounded-full border-2 border-hf-sage border-t-transparent animate-spin shrink-0" />
      )}
      {status === 'awaiting_approval' && (
        <div className="w-2.5 h-2.5 rounded-full bg-hf-warning animate-pulse shrink-0" />
      )}
      {status === 'failed' && (
        <X className="w-3.5 h-3.5 text-hf-danger shrink-0" />
      )}
      {(status === 'future' || status === 'pending') && (
        <div className="w-3.5 h-3.5 shrink-0" />
      )}
      {status === 'skipped' && (
        <div className="w-3.5 h-3.5 shrink-0" />
      )}

      {/* Stage name */}
      <span
        className={cn(
          'truncate',
          status === 'completed' && 'text-hf-fg3',
          status === 'running' && 'font-medium text-hf-fg1',
          status === 'awaiting_approval' && 'font-medium text-hf-fg1',
          status === 'failed' && 'text-hf-danger',
          (status === 'future' || status === 'pending') && 'text-hf-fg4',
          status === 'skipped' && 'text-hf-fg3',
        )}
      >
        {name}
        {status === 'skipped' && (
          <span className="ml-1.5 text-xs text-hf-fg3 font-normal">(Skipped)</span>
        )}
      </span>
    </button>
  )
}
