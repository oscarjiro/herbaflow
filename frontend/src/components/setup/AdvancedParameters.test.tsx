/**
 * Unit tests for the STRING confidence preset selector in AdvancedParameters.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AdvancedParameters, DEFAULT_PARAMS } from './AdvancedParameters'

// The Accordion is real but needs no special setup in jsdom.

describe('AdvancedParameters — STRING confidence preset selector', () => {
  it('STRING confidence selector offers Low/Medium/High/Very High presets', () => {
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={() => {}}
      />
    )

    // Open the PPI Network accordion section
    const networkTrigger = screen.getByText('PPI Network')
    fireEvent.click(networkTrigger)

    // All four preset labels must be present (with numeric values)
    expect(screen.getByRole('button', { name: 'Low (0.15)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Medium (0.40)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'High (0.70)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Very High (0.90)' })).toBeInTheDocument()
  })

  it('STRING confidence selector default value is Medium (0.400)', () => {
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={() => {}}
      />
    )

    const networkTrigger = screen.getByText('PPI Network')
    fireEvent.click(networkTrigger)

    // Button preset group: Medium button should have aria-pressed="true"
    const mediumBtn = screen.getByRole('button', { name: 'Medium (0.40)' })
    expect(mediumBtn).toHaveAttribute('aria-pressed', 'true')
  })

  it('STRING confidence selector emits correct decimal value on change', () => {
    const onChange = vi.fn()
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={onChange}
      />
    )

    const networkTrigger = screen.getByText('PPI Network')
    fireEvent.click(networkTrigger)

    // Click "High" preset
    const highBtn = screen.getByRole('button', { name: 'High (0.70)' })
    fireEvent.click(highBtn)

    // onChange must have been called with min_confidence = 0.7
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ min_confidence: 0.7 })
    )
  })
})

describe('AdvancedParameters — PPI Network rename + numeric preset labels', () => {
  it('network accordion trigger reads "PPI Network"', () => {
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={() => {}}
      />
    )

    expect(screen.getByText('PPI Network')).toBeInTheDocument()
  })

  it('confidence preset buttons read Low (0.15), Medium (0.40), High (0.70), Very High (0.90)', () => {
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={() => {}}
      />
    )

    // Open the PPI Network accordion section
    const ppiTrigger = screen.getByText('PPI Network')
    fireEvent.click(ppiTrigger)

    expect(screen.getByRole('button', { name: 'Low (0.15)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Medium (0.40)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'High (0.70)' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Very High (0.90)' })).toBeInTheDocument()
  })
})
