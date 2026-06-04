// PlantSelector.test.tsx
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

import type { PlantResponse } from '@/types/api'

const plants: PlantResponse[] = [
  {
    plant_id: 'plant-1',
    canonical_scientific_name: 'Curcuma longa',
    family_name: 'Zingiberaceae',
    compound_count: 42,
    plant_aliases: ['turmeric'],
  },
  {
    plant_id: 'plant-2',
    canonical_scientific_name: 'Zingiber officinale',
    family_name: 'Zingiberaceae',
    compound_count: 17,
    plant_aliases: ['ginger'],
  },
]

vi.mock('@/hooks/usePlants', () => ({
  usePlants: () => ({ data: plants, isLoading: false }),
}))

import { PlantSelector } from './PlantSelector'

describe('PlantSelector', () => {
  it('renders rows with family_name and a compound-count badge', async () => {
    render(<PlantSelector value={[]} onChange={vi.fn()} />)
    await userEvent.click(screen.getByRole('combobox'))

    // family_name shown on the row
    expect(screen.getAllByText('Zingiberaceae').length).toBeGreaterThan(0)

    // compound count badge with a "compounds" title
    const badge = screen.getByTitle(/42 compounds/i)
    expect(badge).toHaveTextContent('42')
  })

  it('renders a removable selected chip for the selected plant', () => {
    render(<PlantSelector value={['plant-1']} onChange={vi.fn()} />)
    expect(
      screen.getByRole('button', { name: 'Remove Curcuma longa' }),
    ).toBeInTheDocument()
  })

  it('shows an amber soft-cap counter and notice at the soft cap', () => {
    const value = Array.from({ length: 10 }, (_, i) => `p${i}`)
    render(<PlantSelector value={value} onChange={vi.fn()} />)
    const counter = screen.getByText(/10 \/ 20/)
    expect(counter).toHaveClass('text-hf-warning')
    expect(counter).toHaveTextContent(/approaching/i)
  })

  it('disables unselected rows and shows the max notice at the hard cap', async () => {
    const value = Array.from({ length: 20 }, (_, i) => `p${i}`)
    render(<PlantSelector value={value} onChange={vi.fn()} />)

    const notice = screen.getByText(/Maximum 20 plants reached/i)
    expect(notice).toHaveClass('text-hf-warning')

    await userEvent.click(screen.getByRole('combobox'))
    // The 2 mocked fixtures are not among the 20 ids → unselected → disabled.
    const row = screen.getByText('Curcuma longa').closest('[role="option"]')
    expect(row).toHaveAttribute('aria-disabled', 'true')
  })
})
