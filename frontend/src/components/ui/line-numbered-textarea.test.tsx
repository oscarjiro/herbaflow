// line-numbered-textarea.test.tsx
import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { LineNumberedTextarea } from './line-numbered-textarea'

describe('LineNumberedTextarea', () => {
  it('renders one line number per non-empty value line', () => {
    render(<LineNumberedTextarea value={'a\nb\nc'} onChange={() => {}} aria-label="x" />)
    expect(screen.getByTestId('line-nums').children).toHaveLength(3)
  })
  it('renders zero line numbers when empty', () => {
    render(<LineNumberedTextarea value={''} onChange={() => {}} aria-label="x" />)
    expect(screen.getByTestId('line-nums').children).toHaveLength(0)
  })
  it('calls onChange with the new text', async () => {
    const onChange = vi.fn()
    render(<LineNumberedTextarea value={''} onChange={onChange} aria-label="x" />)
    await userEvent.type(screen.getByRole('textbox'), 'X')
    expect(onChange).toHaveBeenCalled()
  })
  it('shows a count and per-line error markers', () => {
    render(
      <LineNumberedTextarea value={'TP53\nbad!'} onChange={() => {}} aria-label="x"
        lineErrors={{ 2: 'not a valid gene symbol' }} count="2 targets" />,
    )
    expect(screen.getByText('2 targets')).toBeInTheDocument()
    expect(screen.getByTestId('line-error-2')).toHaveTextContent('not a valid gene symbol')
  })
  it('renders an amber warning message with the warning token', () => {
    render(<LineNumberedTextarea value={'a'} onChange={() => {}} aria-label="x" warning="x / y soft" />)
    const msg = screen.getByText('x / y soft')
    expect(msg).toBeInTheDocument()
    expect(msg).toHaveClass('text-hf-warning')
  })
  it('prefers the error over the warning when both are passed', () => {
    render(
      <LineNumberedTextarea value={'a'} onChange={() => {}} aria-label="x"
        error="boom" warning="x / y soft" />,
    )
    expect(screen.getByText('boom')).toBeInTheDocument()
    expect(screen.queryByText('x / y soft')).not.toBeInTheDocument()
  })
})
