import * as React from 'react'
import { Check, ChevronsUpDown, X } from 'lucide-react'
import Fuse from 'fuse.js'

import { cn } from '@/lib/utils'
import { Button } from '@/components/ui/button'
import {
  Command,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
} from '@/components/ui/command'
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from '@/components/ui/popover'
import { useDiseases } from '@/hooks/useDiseases'
import { formatDiseaseName } from '@/lib/format'

interface DiseaseSelectorProps {
  value: string[]
  onChange: (ids: string[]) => void
}

export function DiseaseSelector({ value, onChange }: DiseaseSelectorProps) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const { data: diseases = [], isLoading } = useDiseases()

  // Reset query when popover closes
  React.useEffect(() => {
    if (!open) setQuery('')
  }, [open])

  // Fuse instance — recreated only when the diseases list changes
  const fuse = React.useMemo(
    () =>
      new Fuse(diseases, {
        keys: [
          { name: 'disease_name', weight: 1.0 },
          { name: 'ontology_id', weight: 0.5 },
          { name: 'disease_aliases', weight: 0.6 },
        ],
        threshold: 0.4,
        includeScore: true,
      }),
    [diseases],
  )

  // Fuzzy-filtered list — if no query, show all diseases
  const filtered = React.useMemo(() => {
    if (!query.trim()) return diseases
    return fuse.search(query).map((r) => r.item)
  }, [fuse, query, diseases])

  function toggle(id: string) {
    if (value.includes(id)) {
      onChange(value.filter((v) => v !== id))
    } else {
      onChange([...value, id])
    }
  }

  function remove(id: string) {
    onChange(value.filter((v) => v !== id))
  }

  const selectedDiseases = diseases.filter((d) => value.includes(d.disease_id))
  const orphanedIds = value.filter((id) => !diseases.some((d) => d.disease_id === id))

  return (
    <div className="flex flex-col gap-2">
      <Popover open={open} onOpenChange={setOpen}>
        <PopoverTrigger asChild>
          <Button
            variant="outline"
            role="combobox"
            aria-expanded={open}
            className="w-full justify-between bg-hf-surface border-hf-border text-hf-fg2 rounded-sm"
          >
            <span className={value.length === 0 ? 'text-hf-fg3' : undefined}>
              {value.length === 0
                ? 'Select diseases...'
                : `${value.length} disease${value.length === 1 ? '' : 's'} selected`}
            </span>
            <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
          </Button>
        </PopoverTrigger>
        <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
          {/* shouldFilter={false}: fuse.js handles filtering, not cmdk */}
          <Command shouldFilter={false}>
            <CommandInput
              placeholder="Search diseases..."
              value={query}
              onValueChange={setQuery}
            />
            <CommandList className="max-h-64">
              {isLoading && (
                <CommandEmpty>Loading diseases...</CommandEmpty>
              )}
              {!isLoading && filtered.length === 0 && (
                <CommandEmpty>No diseases found.</CommandEmpty>
              )}
              {!isLoading && filtered.length > 0 && (
                <CommandGroup>
                  {filtered.map((disease) => {
                    const isSelected = value.includes(disease.disease_id)
                    return (
                      <CommandItem
                        key={disease.disease_id}
                        value={disease.disease_id}
                        onSelect={() => toggle(disease.disease_id)}
                      >
                        <Check
                          className={cn(
                            'mr-2 h-4 w-4 shrink-0',
                            isSelected ? 'opacity-100' : 'opacity-0'
                          )}
                        />
                        <div className="flex flex-col min-w-0">
                          <span className="text-sm text-hf-fg1 truncate">
                            {formatDiseaseName(disease.disease_name)}
                          </span>
                          {disease.ontology_id && (
                            <span className="text-xs text-hf-fg3">
                              {disease.ontology_id}
                            </span>
                          )}
                        </div>
                      </CommandItem>
                    )
                  })}
                </CommandGroup>
              )}
            </CommandList>
          </Command>
        </PopoverContent>
      </Popover>

      {(selectedDiseases.length > 0 || orphanedIds.length > 0) && (
        <div className="flex flex-wrap gap-1.5">
          {selectedDiseases.map((disease) => (
            <span
              key={disease.disease_id}
              className="inline-flex items-center gap-1 rounded-sm bg-hf-sage-faint border border-hf-border px-2 py-0.5 text-xs text-hf-fg1"
            >
              <span>{formatDiseaseName(disease.disease_name)}</span>
              <button
                type="button"
                onClick={() => remove(disease.disease_id)}
                className="text-hf-fg3 hover:text-hf-fg1 transition-colors"
                aria-label={`Remove ${disease.disease_name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
          {orphanedIds.map((id) => (
            <span
              key={id}
              className="inline-flex items-center gap-1 rounded-sm bg-hf-surface border border-hf-border px-2 py-0.5 text-xs text-hf-fg3"
            >
              <span>Unknown ({id})</span>
              <button
                type="button"
                onClick={() => remove(id)}
                className="text-hf-fg3 hover:text-hf-fg1 transition-colors"
                aria-label={`Remove unknown disease ${id}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  )
}
