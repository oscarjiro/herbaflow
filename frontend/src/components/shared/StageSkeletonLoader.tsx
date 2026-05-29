// Animated skeleton loader shown when a stage is running (status = stage_N_running).
// Rendered by StagePanelRouter — no changes needed in individual stage panels.

const STAGE_NAMES: Record<number, string> = {
  1: 'Compound Selection',
  2: 'ADME Filtering',
  3: 'Target Identification',
  4: 'Disease Targets',
  5: 'Target Overlap',
  6: 'PPI Network',
  7: 'Hub Gene Analysis',
  8: 'Pathway Enrichment',
}

// Number of stat cards to render per stage (matches each panel's grid)
const STAGE_STAT_CARDS: Record<number, number> = {
  1: 3,
  2: 4,
  3: 3,
  4: 3,
  5: 3,
  6: 3,
  7: 3,
  8: 3,
}

const GRID_CLASS: Record<number, string> = {
  2: 'grid-cols-2',
  3: 'grid-cols-3',
  4: 'grid-cols-4',
}

interface StageSkeletonLoaderProps {
  stage: number
  /** Optional progress label, e.g. "Identifying targets…" */
  progressText?: string
}

function SkeletonBar({ className = '' }: { className?: string }) {
  return (
    <div
      className={`animate-pulse rounded bg-hf-border ${className}`}
      aria-hidden="true"
    />
  )
}

export function StageSkeletonLoader({ stage, progressText }: StageSkeletonLoaderProps) {
  const stageName = STAGE_NAMES[stage] ?? `Stage ${stage}`
  const statCount = STAGE_STAT_CARDS[stage] ?? 3
  const gridClass = GRID_CLASS[statCount] ?? 'grid-cols-3'

  return (
    <div className="space-y-6" aria-label={`Stage ${stage} loading`} aria-busy="true">
      {/* Header row — matches StageHeader layout */}
      <div className="mb-6 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <SkeletonBar className="h-3 w-12" />
          <SkeletonBar className="h-5 w-44" />
          <SkeletonBar className="h-5 w-16 rounded-full" />
        </div>
        <SkeletonBar className="h-3 w-10" />
      </div>

      {/* Optional progress text */}
      {progressText && (
        <p className="animate-pulse text-sm text-hf-fg2">{progressText}</p>
      )}

      {/* Stat cards */}
      <div className={`grid gap-4 ${gridClass}`}>
        {Array.from({ length: statCount }).map((_, i) => (
          <div
            key={i}
            className="rounded-lg border border-hf-border bg-hf-surface p-4 space-y-3"
          >
            <SkeletonBar className="h-3 w-24" />
            <SkeletonBar className="h-8 w-16" />
          </div>
        ))}
      </div>

      {/* Table skeleton */}
      <div className="rounded-lg border border-hf-border overflow-hidden">
        {/* Column headers */}
        <div className="flex gap-6 bg-hf-surface px-4 py-3 border-b border-hf-border">
          <SkeletonBar className="h-3 w-36" />
          <SkeletonBar className="h-3 w-24" />
          <SkeletonBar className="h-3 w-28" />
          <SkeletonBar className="h-3 w-20" />
        </div>
        {/* Rows */}
        {Array.from({ length: 6 }).map((_, i) => (
          <div
            key={i}
            className="flex gap-6 px-4 py-3 border-b border-hf-border last:border-b-0"
          >
            <SkeletonBar className="h-3 w-40" />
            <SkeletonBar className="h-3 w-20" />
            <SkeletonBar className="h-3 w-32" />
            <SkeletonBar className="h-3 w-16" />
          </div>
        ))}
      </div>

      {/* Running indicator */}
      <p className="flex items-center gap-2 text-xs text-hf-fg3">
        <span
          className="inline-block h-2 w-2 rounded-full bg-hf-warning animate-pulse"
          aria-hidden="true"
        />
        Running {stageName}…
      </p>
    </div>
  )
}
