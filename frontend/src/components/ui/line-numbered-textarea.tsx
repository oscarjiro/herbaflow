import * as React from 'react'
import { cn } from '@/lib/utils'

interface LineNumberedTextareaProps {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  error?: string                       // whole-field error (border + message)
  warning?: string                     // amber soft-cap message (no border change)
  lineErrors?: Record<number, string>  // 1-based line -> message
  count?: string                       // e.g. "12 targets entered"
  'aria-label': string
}

/**
 * Multi-line input with a synced line-number gutter.
 *
 * The box has a FIXED height and scrolls internally — it never grows with the
 * content. The gutter shares the textarea's vertical padding and line-height and
 * mirrors its scrollTop, so line numbers stay aligned no matter how far you scroll.
 * Per-line errors collapse into a single "N issues" summary that expands on demand,
 * so a list with hundreds of bad lines doesn't flood the form with messages.
 */
export function LineNumberedTextarea(p: LineNumberedTextareaProps) {
  const taRef = React.useRef<HTMLTextAreaElement>(null)
  const lnRef = React.useRef<HTMLDivElement>(null)
  const lines = p.value === '' ? [] : p.value.split('\n')
  const lineErrorEntries = p.lineErrors ? Object.entries(p.lineErrors) : []
  const hasError = Boolean(p.error) || lineErrorEntries.length > 0

  return (
    <div>
      <div className={cn('relative flex h-44 overflow-hidden rounded-md border bg-hf-bg font-mono text-sm',
        hasError ? 'border-hf-danger' : 'border-hf-border')}>
        <div
          ref={lnRef}
          data-testid="line-nums"
          className="select-none overflow-hidden px-3 py-3 text-right text-hf-fg3"
          style={{ minWidth: '2.5rem' }}
          aria-hidden="true"
        >
          {lines.map((_, i) => (
            <div key={i} className={cn('h-6 leading-6', p.lineErrors?.[i + 1] && 'text-hf-danger')}>
              {i + 1}
            </div>
          ))}
        </div>
        <textarea
          ref={taRef}
          aria-label={p['aria-label']}
          value={p.value}
          placeholder={p.placeholder}
          onChange={(e) => p.onChange(e.target.value)}
          onScroll={() => { if (taRef.current && lnRef.current) lnRef.current.scrollTop = taRef.current.scrollTop }}
          className="h-full flex-1 resize-none overflow-y-auto rounded-r-md border-0 bg-hf-bg p-3 leading-6 text-hf-fg1 placeholder:text-hf-fg3 focus:outline-none"
        />
      </div>
      {p.error ? (
        <p className="mt-1 text-xs text-hf-danger">{p.error}</p>
      ) : p.warning ? (
        <p className="mt-1 text-xs text-hf-warning">{p.warning}</p>
      ) : p.count ? (
        <p className="mt-1 text-xs text-hf-fg3">{p.count}</p>
      ) : null}
      {lineErrorEntries.length > 0 && (
        <details className="mt-1" data-testid="line-errors">
          <summary className="cursor-pointer text-xs text-hf-danger">
            {lineErrorEntries.length} {lineErrorEntries.length === 1 ? 'issue' : 'issues'} found — click to view
          </summary>
          <ul className="mt-1 space-y-0.5">
            {lineErrorEntries.map(([ln, msg]) => (
              <li key={ln} data-testid={`line-error-${ln}`} className="text-xs text-hf-danger">
                Line {ln}: {msg}
              </li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
