import { render, screen } from '@testing-library/react'
import { StatusBadge } from '@/components/shared/StatusBadge'

describe('StatusBadge', () => {
  it('shows info color for running status', () => {
    const { container } = render(<StatusBadge status="stage_2_running" />)
    expect(container.firstChild).toHaveClass('bg-hf-info-soft')
  })

  it('shows warning color for awaiting_approval', () => {
    const { container } = render(<StatusBadge status="stage_3_awaiting_approval" />)
    expect(container.firstChild).toHaveClass('bg-hf-warning-soft')
  })

  it('shows success color for complete', () => {
    const { container } = render(<StatusBadge status="complete" />)
    expect(container.firstChild).toHaveClass('bg-hf-success-soft')
  })

  it('shows danger color for failed', () => {
    const { container } = render(<StatusBadge status="failed" />)
    expect(container.firstChild).toHaveClass('bg-hf-danger-soft')
  })

  it('uses label override when provided', () => {
    render(<StatusBadge status="complete" label="Done" />)
    expect(screen.getByText('Done')).toBeInTheDocument()
  })
})
