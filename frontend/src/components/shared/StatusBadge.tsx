import { cn } from '@/lib/utils'
import type { AnalysisStatus } from '@/types/api'

type BadgeVariant = 'info' | 'warning' | 'success' | 'danger' | 'neutral'

function getVariant(status: string): BadgeVariant {
  if (status.includes('running')) return 'info'
  if (status.includes('awaiting_approval')) return 'warning'
  if (status === 'complete' || status.includes('_complete')) return 'success'
  if (status === 'failed' || status.includes('_failed') || status.includes('rejected')) return 'danger'
  return 'neutral'
}

const variantClasses: Record<BadgeVariant, string> = {
  info:    'bg-hf-info-soft text-hf-info',
  warning: 'bg-hf-warning-soft text-hf-warning',
  success: 'bg-hf-success-soft text-hf-success',
  danger:  'bg-hf-danger-soft text-hf-danger',
  neutral: 'bg-hf-surface-2 text-hf-fg3',
}

interface StatusBadgeProps {
  status: AnalysisStatus | string
  label?: string
  className?: string
}

export function StatusBadge({ status, label, className }: StatusBadgeProps) {
  const variant = getVariant(status)
  return (
    <span className={cn(
      'inline-flex items-center rounded px-2 py-0.5 text-xs font-medium font-sans',
      variantClasses[variant],
      className
    )}>
      {label ?? status.replace(/_/g, ' ')}
    </span>
  )
}
