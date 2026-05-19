import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import SetupPage from '@/pages/SetupPage'

// ============================================================================
// Test wrapper
// ============================================================================

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/setup']}>
        {children}
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// ============================================================================
// Tests
// ============================================================================

describe('SetupPage', () => {
  it('renders all form sections', async () => {
    render(<SetupPage />, { wrapper })

    // Heading
    expect(screen.getByText('New Analysis')).toBeInTheDocument()

    // Section labels
    expect(screen.getByText('Plants')).toBeInTheDocument()
    expect(screen.getByText('Disease')).toBeInTheDocument()
    expect(screen.getByText('Mode')).toBeInTheDocument()
    expect(screen.getByText('Analysis Name')).toBeInTheDocument()
    expect(screen.getByText('Advanced Parameters')).toBeInTheDocument()

    // Submit button exists and is disabled (no selection yet)
    const btn = screen.getByRole('button', { name: /start analysis/i })
    expect(btn).toBeDisabled()
  })

  it('submit button is disabled with no plants or disease selected', () => {
    render(<SetupPage />, { wrapper })
    const btn = screen.getByRole('button', { name: /start analysis/i })
    expect(btn).toBeDisabled()
  })

  it('renders analysis name input with a default value', () => {
    render(<SetupPage />, { wrapper })
    const input = screen.getByPlaceholderText('Enter analysis name')
    expect(input).toBeInTheDocument()
    // Default name includes today's date prefix
    expect((input as HTMLInputElement).value).toMatch(/^Analysis —/)
  })
})
