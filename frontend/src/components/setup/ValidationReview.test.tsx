import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ValidationReview } from './ValidationReview'

const result = {
  valid: Array.from({ length: 47 }, (_, i) => ({ id: i })),
  failed: [
    { line: 4, input: 'bad!', reason: 'not a valid gene symbol or UniProt accession' },
    { line: 9, input: 'xx', reason: 'not found in PubChem' },
    { line: 12, input: '???', reason: 'invalid' },
  ],
  normalized: [{ from: 'p53', to: 'TP53' }],
  duplicates: ['TP53', 'EGFR'],
  reused: 10,
  enriched: 37,
}

describe('ValidationReview', () => {
  it('summarizes ready count, failures, duplicates, and wires the buttons', async () => {
    const onContinue = vi.fn()
    const onBack = vi.fn()
    render(
      <ValidationReview
        scopes={[{ label: 'Targets', total: 52, result: result as never }]}
        onContinue={onContinue}
        onBack={onBack}
      />,
    )

    expect(screen.getByText(/47 ready/i)).toBeInTheDocument()
    expect(screen.getByText(/not found in PubChem/i)).toBeInTheDocument()
    expect(screen.getByText(/line 9/i)).toBeInTheDocument()
    expect(screen.getByText(/TP53 entered 2×/i)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: /continue \(47\)/i }))
    expect(onContinue).toHaveBeenCalled()
    await userEvent.click(screen.getByRole('button', { name: /go back/i }))
    expect(onBack).toHaveBeenCalled()
  })

  it('renders normalized from → to entries', () => {
    render(
      <ValidationReview
        scopes={[{ label: 'Targets', total: 52, result: result as never }]}
        onContinue={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    expect(screen.getByText(/p53\s*→\s*TP53/i)).toBeInTheDocument()
  })

  it('counts a duplicate value appearing twice as entered 3×', () => {
    const r = { ...result, duplicates: ['EGFR', 'EGFR'] }
    render(
      <ValidationReview
        scopes={[{ label: 'Targets', total: 52, result: r as never }]}
        onContinue={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    // EGFR appears twice in duplicates → 2 extra entries beyond the first → "3×"
    expect(screen.getByText(/EGFR entered 3×/i)).toBeInTheDocument()
  })

  it('renders one labeled section per scope and sums ready across scopes', () => {
    const targets = { ...result, valid: [{ id: 1 }, { id: 2 }], duplicates: [], failed: [], normalized: [] }
    const disease = { ...result, valid: [{ id: 3 }], duplicates: [], failed: [], normalized: [] }
    render(
      <ValidationReview
        scopes={[
          { label: 'Compound targets', total: 2, result: targets as never },
          { label: 'Disease targets', total: 1, result: disease as never },
        ]}
        onContinue={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    // Both scope labels are shown when there is more than one section.
    expect(screen.getByText('Compound targets')).toBeInTheDocument()
    expect(screen.getByText('Disease targets')).toBeInTheDocument()
    expect(screen.getAllByTestId('review-section')).toHaveLength(2)
    // Continue reflects the combined ready count (2 + 1).
    expect(screen.getByRole('button', { name: /continue \(3\)/i })).toBeInTheDocument()
  })

  it('reports reused as "already in database" (no "cache" wording)', () => {
    render(
      <ValidationReview
        scopes={[{ label: 'Targets', total: 52, result: result as never }]}
        onContinue={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    expect(screen.getByText(/already in database/i)).toBeInTheDocument()
    expect(screen.queryByText(/reused/i)).not.toBeInTheDocument()
  })
})
