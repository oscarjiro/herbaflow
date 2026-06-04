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
        result={result as never}
        total={52}
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
        result={result as never}
        total={52}
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
        result={r as never}
        total={52}
        onContinue={vi.fn()}
        onBack={vi.fn()}
      />,
    )
    // EGFR appears twice in duplicates → 2 extra entries beyond the first → "3×"
    expect(screen.getByText(/EGFR entered 3×/i)).toBeInTheDocument()
  })
})
