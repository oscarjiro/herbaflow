import * as React from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'
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
  value: string | null
  onChange: (id: string | null) => void
}

export function DiseaseSelector({ value, onChange }: DiseaseSelectorProps) {
  const [open, setOpen] = React.useState(false)
  const [query, setQuery] = React.useState('')
  const { data: diseases = [], isLoading } = useDiseases()

  React.useEffect(() => {
    if (!open) setQuery('')
  }, [open])

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

  const filtered = React.useMemo(() => {
    if (!query.trim()) return diseases
    return fuse.search(query).map((r) => r.item)
  }, [fuse, query, diseases])

  const selected = diseases.find((d) => d.disease_id === value) ?? null

  function select(id: string) {
    onChange(id === value ? null : id)
    setOpen(false)
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full justify-between bg-hf-surface border-hf-border text-hf-fg2 rounded-sm"
        >
          <span className={value ? undefined : 'text-hf-fg3'}>
            {selected
              ? formatDiseaseName(selected.disease_name)
              : value
                ? `Unknown (${value})`
                : 'Select a disease...'}
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
            {isLoading && <CommandEmpty>Loading diseases...</CommandEmpty>}
            {!isLoading && filtered.length === 0 && (
              <CommandEmpty>No diseases found.</CommandEmpty>
            )}
            {!isLoading && filtered.length > 0 && (
              <CommandGroup>
                {filtered.map((disease) => {
                  const isSelected = disease.disease_id === value
                  return (
                    <CommandItem
                      key={disease.disease_id}
                      value={disease.disease_id}
                      onSelect={() => select(disease.disease_id)}
                    >
                      <Check
                        className={cn(
                          'mr-2 h-4 w-4 shrink-0',
                          isSelected ? 'opacity-100' : 'opacity-0',
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
  )
}
