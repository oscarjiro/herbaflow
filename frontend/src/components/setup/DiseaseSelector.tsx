import * as React from 'react'
import { Check, ChevronsUpDown } from 'lucide-react'

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

interface DiseaseSelectorProps {
  value: string | null
  onChange: (id: string | null) => void
}

export function DiseaseSelector({ value, onChange }: DiseaseSelectorProps) {
  const [open, setOpen] = React.useState(false)
  const { data: diseases = [], isLoading } = useDiseases()

  const selected = diseases.find((d) => d.disease_id === value) ?? null

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
            {selected ? selected.disease_name : 'Select disease...'}
          </span>
          <ChevronsUpDown className="ml-2 h-4 w-4 shrink-0 opacity-50" />
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-[var(--radix-popover-trigger-width)] p-0" align="start">
        <Command>
          <CommandInput placeholder="Search diseases..." />
          <CommandList className="max-h-64">
            {isLoading && (
              <CommandEmpty>Loading diseases...</CommandEmpty>
            )}
            {!isLoading && diseases.length === 0 && (
              <CommandEmpty>No diseases found.</CommandEmpty>
            )}
            {!isLoading && diseases.length > 0 && (
              <CommandGroup>
                {diseases.map((disease) => {
                  const isSelected = value === disease.disease_id
                  return (
                    <CommandItem
                      key={disease.disease_id}
                      value={`${disease.disease_name} ${disease.ontology_id ?? ''}`}
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
                          {disease.disease_name}
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
