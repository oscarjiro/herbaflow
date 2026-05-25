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

  const selected = diseases.find((d) => d.disease_id === value) ?? null

  // Reset query when popover closes
  React.useEffect(() => {
    if (!open) setQuery('')
  }, [open])

  // Fuse instance — recreated only when the diseases list changes
  const fuse = React.useMemo(
    () =>
      new Fuse(diseases, {
        keys: ['disease_name', 'ontology_id'],
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

  function handleSelect(id: string) {
    // Selecting the same item deselects
    onChange(value === id ? null : id)
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
          <span className={selected == null ? 'text-hf-fg3' : 'text-hf-fg1'}>
            {selected
              ? formatDiseaseName(selected.disease_name)
              : 'Select disease...'}
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
                  const isSelected = value === disease.disease_id
                  return (
                    <CommandItem
                      key={disease.disease_id}
                      value={disease.disease_id}
                      onSelect={() => handleSelect(disease.disease_id)}
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
  )
}
