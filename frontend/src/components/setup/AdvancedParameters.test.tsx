/**
 * Unit tests for the STRING confidence preset selector in AdvancedParameters.
 */
import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { AdvancedParameters, DEFAULT_PARAMS } from './AdvancedParameters'

// The Accordion is real but needs no special setup in jsdom.

describe('AdvancedParameters — STRING confidence preset selector', () => {
  it('STRING confidence selector offers Low/Medium/High/Highest presets', () => {
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={() => {}}
      />
    )

    // Open the Network accordion section
    const networkTrigger = screen.getByText('Network')
    fireEvent.click(networkTrigger)

    // All four preset labels must be present
    expect(screen.getByText('Low')).toBeInTheDocument()
    expect(screen.getByText('Medium')).toBeInTheDocument()
    expect(screen.getByText('High')).toBeInTheDocument()
    expect(screen.getByText('Highest')).toBeInTheDocument()
  })

  it('STRING confidence selector default value is Medium (0.400)', () => {
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={() => {}}
      />
    )

    const networkTrigger = screen.getByText('Network')
    fireEvent.click(networkTrigger)

    // The selector (select element or button group) should show Medium as selected/active
    // We look for a <select> with value 0.4, or a button with aria-pressed=true labeled Medium
    const selector = screen.queryByRole('combobox')
    if (selector) {
      expect((selector as HTMLSelectElement).value).toBe('0.4')
    } else {
      // Button preset group: Medium button should have aria-pressed="true"
      const mediumBtn = screen.getByRole('button', { name: 'Medium' })
      expect(mediumBtn).toHaveAttribute('aria-pressed', 'true')
    }
  })

  it('STRING confidence selector emits correct decimal value on change', () => {
    const onChange = vi.fn()
    render(
      <AdvancedParameters
        value={DEFAULT_PARAMS}
        onChange={onChange}
      />
    )

    const networkTrigger = screen.getByText('Network')
    fireEvent.click(networkTrigger)

    // Click "High" preset
    const selector = screen.queryByRole('combobox')
    if (selector) {
      fireEvent.change(selector, { target: { value: '0.7' } })
    } else {
      const highBtn = screen.getByRole('button', { name: 'High' })
      fireEvent.click(highBtn)
    }

    // onChange must have been called with min_confidence = 0.7
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ min_confidence: 0.7 })
    )
  })
})
