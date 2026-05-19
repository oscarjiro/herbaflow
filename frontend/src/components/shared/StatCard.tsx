import { cn } from '@/lib/utils'

interface StatCardProps {
  label: string
  value: string | number
  className?: string
}

export function StatCard({ label, value, className }: StatCardProps) {
  return (
    <div className={cn('rounded-lg border border-hf-border bg-hf-surface p-4', className)}>
      <p className="text-xs text-hf-fg3 font-sans">{label}</p>
      <p className="mt-1 text-2xl font-display text-hf-fg1">{value}</p>
    </div>
  )
}
