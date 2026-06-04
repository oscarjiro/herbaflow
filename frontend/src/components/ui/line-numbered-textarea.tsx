import * as React from 'react'
import { cn } from '@/lib/utils'

interface LineNumberedTextareaProps {
  value: string
  onChange: (v: string) => void
  placeholder?: string
  rows?: number
  error?: string                       // whole-field error (border + message)
  warning?: string                     // amber soft-cap message (no border change)
  lineErrors?: Record<number, string>  // 1-based line -> message
  count?: string                       // e.g. "12 targets entered"
  'aria-label': string
}

export function LineNumberedTextarea(p: LineNumberedTextareaProps) {
  const taRef = React.useRef<HTMLTextAreaElement>(null)
  const lnRef = React.useRef<HTMLDivElement>(null)
  const lines = p.value === '' ? [] : p.value.split('\n')
  const hasError = Boolean(p.error) || (p.lineErrors && Object.keys(p.lineErrors).length > 0)

  return (
    <div>
      <div className={cn('relative flex rounded-md border bg-hf-bg font-mono text-sm',
        hasError ? 'border-hf-danger' : 'border-hf-border')}>
        <div
          ref={lnRef}
          data-testid="line-nums"
          className="select-none overflow-hidden pt-3 pl-3 pr-3 text-right text-hf-fg3"
          style={{ minWidth: '2.5rem' }}
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
          rows={p.rows ?? 6}
          placeholder={p.placeholder}
          onChange={(e) => p.onChange(e.target.value)}
          onScroll={() => { if (taRef.current && lnRef.current) lnRef.current.scrollTop = taRef.current.scrollTop }}
          className="flex-1 resize-y rounded-r-md border-0 bg-hf-bg p-3 leading-6 text-hf-fg1 placeholder:text-hf-fg3 focus:outline-none"
        />
      </div>
      {p.error ? (
        <p className="mt-1 text-xs text-hf-danger">{p.error}</p>
      ) : p.warning ? (
        <p className="mt-1 text-xs text-hf-warning">{p.warning}</p>
      ) : p.count ? (
        <p className="mt-1 text-xs text-hf-fg3">{p.count}</p>
      ) : null}
      {p.lineErrors && Object.entries(p.lineErrors).map(([ln, msg]) => (
        <p key={ln} data-testid={`line-error-${ln}`} className="mt-0.5 text-xs text-hf-danger">
          Line {ln}: {msg}
        </p>
      ))}
    </div>
  )
}
