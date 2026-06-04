import { FlaskConical, X } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { EntityCombobox } from '@/components/ui/entity-combobox'
import { usePlants } from '@/hooks/usePlants'
import type { PlantResponse } from '@/types/api'

interface PlantSelectorProps {
  value: string[]
  onChange: (ids: string[]) => void
}

function renderPlantRow(plant: PlantResponse) {
  return (
    <div className="flex flex-1 items-center justify-between min-w-0">
      <div className="flex flex-col min-w-0">
        <span className="text-sm text-hf-fg1 truncate">
          {plant.canonical_scientific_name}
        </span>
        {plant.family_name && (
          <span className="text-xs text-hf-fg3 truncate">
            {plant.family_name}
          </span>
        )}
      </div>
      <Badge
        variant="secondary"
        className="ml-2 shrink-0 inline-flex items-center gap-1 text-xs"
        title={`${plant.compound_count} compounds in database`}
      >
        <FlaskConical className="h-3 w-3" />
        {plant.compound_count}
      </Badge>
    </div>
  )
}

export function PlantSelector({ value, onChange }: PlantSelectorProps) {
  const { data: plants = [], isLoading } = usePlants()

  const selectedPlants = plants.filter((p) => value.includes(p.plant_id))

  return (
    <div className="flex flex-col gap-2">
      <EntityCombobox<PlantResponse>
        multi
        items={plants}
        value={value}
        onChange={onChange}
        isLoading={isLoading}
        getKey={(p) => p.plant_id}
        getLabel={(p) => p.canonical_scientific_name}
        searchKeys={[
          { name: 'canonical_scientific_name', weight: 1 },
          { name: 'family_name', weight: 0.5 },
          { name: 'plant_aliases', weight: 0.6 },
        ]}
        placeholder="Select plants..."
        triggerLabel={(n) => `${n} plant${n === 1 ? '' : 's'} selected`}
        renderRow={renderPlantRow}
      />

      {selectedPlants.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {selectedPlants.map((plant) => (
            <span
              key={plant.plant_id}
              className="inline-flex items-center gap-1 rounded-sm bg-hf-sage-faint border border-hf-border px-2 py-0.5 text-xs text-hf-fg1"
            >
              <span className="italic">{plant.canonical_scientific_name}</span>
              <button
                type="button"
                onClick={() => onChange(value.filter((v) => v !== plant.plant_id))}
                className="text-hf-fg3 hover:text-hf-fg1 transition-colors"
                aria-label={`Remove ${plant.canonical_scientific_name}`}
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
