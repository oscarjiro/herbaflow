// DiseaseSelector.test.tsx
// jsdom shims required by Radix Popover + cmdk in jsdom
Element.prototype.hasPointerCapture = vi.fn() as unknown as typeof Element.prototype.hasPointerCapture
Element.prototype.scrollIntoView = vi.fn()
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import type { DiseaseResponse } from '@/types/api'

const diseases: DiseaseResponse[] = [
  {
    disease_id: 'disease-1',
    disease_name: 'type 2 diabetes mellitus',
    ontology_id: 'DOID_2843',
    ontology_source: 'DOID',
    disease_aliases: ['T2DM'],
    target_count: 128,
  },
  {
    disease_id: 'disease-2',
    disease_name: 'breast cancer',
    ontology_id: 'DOID_1612',
    ontology_source: 'DOID',
    disease_aliases: [],
    target_count: 64,
  },
]

vi.mock('@/hooks/useDiseases', () => ({
  useDiseases: () => ({ data: diseases, isLoading: false }),
}))

import { DiseaseSelector } from './DiseaseSelector'

describe('DiseaseSelector', () => {
  it('renders rows with a CURIE-formatted ontology id and a target-count badge', async () => {
    render(<DiseaseSelector value={null} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('combobox'))

    // ontology_id rendered via formatCurie: DOID_2843 -> DOID:2843
    expect(screen.getByText('DOID:2843')).toBeInTheDocument()

    // target count badge with a "disease targets" title
    const badge = screen.getByTitle(/128 disease targets/i)
    expect(badge).toHaveTextContent('128')
  })

  it('calls onChange with a bare disease id string (single-select unwrap)', async () => {
    const onChange = vi.fn()
    render(<DiseaseSelector value={null} onChange={onChange} />)
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(screen.getByText('DOID:2843'))
    expect(onChange).toHaveBeenCalledWith('disease-1')
  })
})
