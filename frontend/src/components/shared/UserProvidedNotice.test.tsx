import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { UserProvidedNotice } from './UserProvidedNotice'

describe('UserProvidedNotice', () => {
  it('shows the manual badge and rejected/normalized counts', () => {
    render(
      <UserProvidedNotice
        inputs={{ rejected: ['XYZZY', 'FOO'], normalized: [{ from: 'AKT', to: 'AKT1' }], unrecognized: [] }}
      />,
    )
    expect(screen.getByText(/provided manually/i)).toBeInTheDocument()
    expect(screen.getByText(/2 not validated/i)).toBeInTheDocument()
    expect(screen.getByText(/AKT → AKT1/)).toBeInTheDocument()
  })

  it('renders the badge alone when there are no issues', () => {
    render(<UserProvidedNotice inputs={null} />)
    expect(screen.getByText(/provided manually/i)).toBeInTheDocument()
    expect(screen.queryByText(/not validated/i)).not.toBeInTheDocument()
  })
})
