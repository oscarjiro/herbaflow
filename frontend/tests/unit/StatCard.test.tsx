import { render, screen } from '@testing-library/react'
import { StatCard } from '@/components/shared/StatCard'

describe('StatCard', () => {
  it('renders value and label', () => {
    render(<StatCard label="Total compounds" value={42} />)
    expect(screen.getByText('Total compounds')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders string value', () => {
    render(<StatCard label="Coverage" value="85.7%" />)
    expect(screen.getByText('85.7%')).toBeInTheDocument()
  })
})
