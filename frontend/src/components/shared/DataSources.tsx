import { useState } from 'react'
import { ChevronDown } from 'lucide-react'
import { cn } from '@/lib/utils'

export interface DataSource {
  name: string
  url: string
  description: string
  citation?: string
}

interface DataSourcesProps {
  sources: DataSource[]
}

export function DataSources({ sources }: DataSourcesProps) {
  const [open, setOpen] = useState(false)

  return (
    <div className="border border-hf-border rounded-lg overflow-hidden text-xs font-sans">
      <button
        type="button"
        onClick={() => setOpen((prev) => !prev)}
        className="w-full flex items-center justify-between px-4 py-2.5 text-left text-xs font-medium text-hf-fg2 hover:text-hf-fg1 hover:bg-hf-border/30 transition-colors"
      >
        <span>Data Sources</span>
        <ChevronDown
          className={cn(
            'w-3.5 h-3.5 text-hf-fg3 transition-transform duration-200',
            open && 'rotate-180',
          )}
        />
      </button>

      {open && (
        <div className="border-t border-hf-border divide-y divide-hf-border">
          {sources.map((src) => (
            <div key={src.name} className="px-4 py-3 space-y-0.5">
              <a
                href={src.url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-medium text-hf-fg1 hover:underline underline-offset-2 inline-flex items-center gap-1"
              >
                {src.name}
                <span className="text-hf-fg3">↗</span>
              </a>
              <p className="text-hf-fg3">{src.description}</p>
              {src.citation && (
                <p className="text-hf-fg3 italic">{src.citation}</p>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
