import type { StageInputs } from '@/types/api'

interface UserProvidedNoticeProps {
  inputs: StageInputs | null
}

export function UserProvidedNotice({ inputs }: UserProvidedNoticeProps) {
  const rejected = inputs?.rejected ?? []
  const normalized = inputs?.normalized ?? []
  const unrecognized = inputs?.unrecognized ?? []

  return (
    <div className="mb-4 rounded-md border border-hf-border bg-hf-surface px-4 py-3 text-sm">
      <span className="inline-flex items-center rounded bg-hf-surface-2 px-2 py-0.5 text-xs font-medium text-hf-fg2">
        Provided manually
      </span>
      {rejected.length > 0 && (
        <p className="mt-2 text-hf-danger">
          ⚠ {rejected.length} not validated: {rejected.join(', ')}
        </p>
      )}
      {unrecognized.length > 0 && (
        <p className="mt-1 text-hf-fg2">
          {unrecognized.length} unrecognized: {unrecognized.join(', ')}
        </p>
      )}
      {normalized.length > 0 && (
        <p className="mt-1 text-hf-fg2">
          {normalized.length} normalized: {normalized.map((n) => `${n.from} → ${n.to}`).join(', ')}
        </p>
      )}
    </div>
  )
}
