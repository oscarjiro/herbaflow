import { Target } from 'lucide-react'

import { Badge } from '@/components/ui/badge'
import { EntityCombobox } from '@/components/ui/entity-combobox'
import { useDiseases } from '@/hooks/useDiseases'
import { formatCurie, formatDiseaseName } from '@/lib/format'
import type { DiseaseResponse } from '@/types/api'

interface DiseaseSelectorProps {
  value: string | null
  onChange: (id: string | null) => void
}

function renderDiseaseRow(disease: DiseaseResponse) {
  return (
    <div className="flex flex-1 items-center justify-between min-w-0">
      <div className="flex flex-col min-w-0">
        <span className="text-sm text-hf-fg1 truncate">
          {formatDiseaseName(disease.disease_name)}
        </span>
        {disease.ontology_id && (
          <span className="text-xs text-hf-fg3">
            {formatCurie(disease.ontology_id)}
          </span>
        )}
      </div>
      <Badge
        variant="secondary"
        className="ml-2 shrink-0 inline-flex items-center gap-1 text-xs"
        title={`${disease.target_count} disease targets (in database, pre-filter)`}
      >
        <Target className="h-3 w-3" />
        {disease.target_count}
      </Badge>
    </div>
  )
}

export function DiseaseSelector({ value, onChange }: DiseaseSelectorProps) {
  const { data: diseases = [], isLoading } = useDiseases()
  const selected = diseases.find((d) => d.disease_id === value) ?? null

  return (
    <EntityCombobox<DiseaseResponse>
      items={diseases}
      value={value ? [value] : []}
      onChange={(keys) => onChange(keys[0] ?? null)}
      isLoading={isLoading}
      getKey={(d) => d.disease_id}
      getLabel={(d) => d.disease_name}
      searchKeys={[
        { name: 'disease_name', weight: 1 },
        { name: 'ontology_id', weight: 0.5 },
        { name: 'disease_aliases', weight: 0.6 },
      ]}
      placeholder="Select a disease..."
      triggerLabel={() =>
        selected ? formatDiseaseName(selected.disease_name) : `Unknown (${value})`
      }
      renderRow={renderDiseaseRow}
    />
  )
}
