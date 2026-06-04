import { SegmentedToggle } from '@/components/ui/segmented-toggle'
import type { AnalysisMode } from '@/types/api'

interface ModeToggleProps {
  value: AnalysisMode
  onChange: (mode: AnalysisMode) => void
}

export function ModeToggle({ value, onChange }: ModeToggleProps) {
  return (
    <SegmentedToggle<AnalysisMode>
      ariaLabel="Analysis mode"
      value={value}
      onChange={onChange}
      options={[
        { value: 'guided', label: 'Guided', description: 'Manual approval at each stage' },
        { value: 'auto', label: 'Auto', description: 'Fully automatic' },
      ]}
    />
  )
}
