import { Button } from '@/components/ui/button'
import type { ValidationPayload } from '@/lib/api'

/** One reviewable scope (e.g. compounds, compound targets, disease targets). */
export interface ReviewSection {
  label: string
  total: number
  result: ValidationPayload
}

interface ValidationReviewProps {
  scopes: ReviewSection[]
  onContinue: () => void
  onBack: () => void
}

/** Group a flat list of duplicate values into [value, totalTimesEntered] pairs. */
function groupDuplicates(duplicates: string[]): [string, number][] {
  const counts = new Map<string, number>()
  for (const value of duplicates) {
    counts.set(value, (counts.get(value) ?? 0) + 1)
  }
  // A value appearing n times in `duplicates` was entered n + 1 times total
  // (the n flagged duplicates plus the first accepted occurrence).
  return [...counts.entries()].map(([value, n]) => [value, n + 1])
}

/** Render one scope's validation result (summary + normalized / failed / duplicates). */
function SectionView({ section, showLabel }: { section: ReviewSection; showLabel: boolean }) {
  const { result, total } = section
  const readyCount = result.valid.length
  const groupedDuplicates = groupDuplicates(result.duplicates)

  return (
    <div data-testid="review-section">
      {showLabel && (
        <p className="text-xs font-semibold uppercase tracking-wide text-hf-fg2 mb-1">
          {section.label}
        </p>
      )}

      {/* Summary */}
      <p className="text-sm text-hf-fg1">
        <span className="font-medium">{readyCount} ready</span>
        {' '}of {total} entered
        {(result.reused > 0 || result.enriched > 0) && (
          <span className="text-hf-fg3">
            {' '}— {result.reused} already in database, {result.enriched} newly enriched
          </span>
        )}
      </p>

      {/* Normalized */}
      {result.normalized.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-hf-fg2 mb-1">Normalized</p>
          <ul className="text-xs text-hf-fg3 space-y-0.5">
            {result.normalized.map((n, i) => (
              <li key={`${n.from}-${i}`}>
                {n.from} → {n.to}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Failures (danger tone) */}
      {result.failed.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-hf-danger mb-1">
            {result.failed.length} could not be validated
          </p>
          <ul className="text-xs text-hf-danger space-y-0.5">
            {result.failed.map((f, i) => (
              <li key={`${f.line}-${i}`}>
                Line {f.line}: {f.input} — {f.reason}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Duplicates (warning tone) */}
      {groupedDuplicates.length > 0 && (
        <div className="mt-3">
          <p className="text-xs font-medium text-hf-warning mb-1">Duplicates</p>
          <ul className="text-xs text-hf-warning space-y-0.5">
            {groupedDuplicates.map(([value, count]) => (
              <li key={value}>
                {value} entered {count}×
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

/**
 * Presentational review of a validate-before-commit pass.
 *
 * Shows one section per manual scope (compounds, compound targets, disease
 * targets): how many inputs are ready, what failed and why, which values were
 * entered more than once, and any normalization the server applied — then lets
 * the user continue (start the run) or go back to editing.
 */
export function ValidationReview({ scopes, onContinue, onBack }: ValidationReviewProps) {
  const totalReady = scopes.reduce((n, s) => n + s.result.valid.length, 0)
  const showLabels = scopes.length > 1

  return (
    <div
      className="bg-hf-surface rounded-lg border border-hf-border p-6 mb-4"
      data-testid="validation-review"
    >
      <p className="text-sm font-medium text-hf-fg2 mb-3">Review inputs</p>

      <div className="space-y-4">
        {scopes.map((section) => (
          <SectionView key={section.label} section={section} showLabel={showLabels} />
        ))}
      </div>

      {/* Actions */}
      <div className="flex gap-2 mt-6">
        <Button variant="outline" onClick={onBack}>
          Go back
        </Button>
        <Button className="flex-1" onClick={onContinue}>
          Continue ({totalReady})
        </Button>
      </div>
    </div>
  )
}
