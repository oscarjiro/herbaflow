import { StatusBadge } from './StatusBadge'

interface StageHeaderProps {
  stage: number
  name: string
  status: string
  elapsedSeconds?: number | null
}

export function StageHeader({ stage, name, status, elapsedSeconds }: StageHeaderProps) {
  return (
    <div className="mb-6 flex items-center justify-between">
      <div className="flex items-center gap-3">
        <span className="text-xs font-mono text-hf-fg4">Stage {stage}</span>
        <h2 className="font-display text-xl text-hf-fg1">{name}</h2>
        <StatusBadge status={status} />
      </div>
      {elapsedSeconds != null && (
        <span className="text-xs text-hf-fg4 font-mono">{elapsedSeconds.toFixed(1)}s</span>
      )}
    </div>
  )
}
