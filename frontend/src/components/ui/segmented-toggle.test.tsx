// segmented-toggle.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SegmentedToggle } from './segmented-toggle'

const opts = [
  { value: 'a', label: 'Alpha' },
  { value: 'b', label: 'Beta' },
]

describe('SegmentedToggle', () => {
  it('marks the active option with aria-pressed and the ink token', () => {
    render(<SegmentedToggle ariaLabel="t" options={opts} value="a" onChange={() => {}} />)
    const active = screen.getByRole('button', { name: 'Alpha' })
    expect(active).toHaveAttribute('aria-pressed', 'true')
    expect(active.className).toContain('bg-hf-fg1')
    expect(active.className).not.toContain('hf-accent') // dead token must not return
  })

  it('calls onChange with the clicked value', async () => {
    const onChange = vi.fn()
    render(<SegmentedToggle ariaLabel="t" options={opts} value="a" onChange={onChange} />)
    await userEvent.click(screen.getByRole('button', { name: 'Beta' }))
    expect(onChange).toHaveBeenCalledWith('b')
  })

  it('renders an optional per-option description', () => {
    render(
      <SegmentedToggle
        ariaLabel="t"
        options={[{ value: 'a', label: 'Alpha', description: 'first' }]}
        value="a"
        onChange={() => {}}
      />,
    )
    expect(screen.getByText('first')).toBeInTheDocument()
  })
})
