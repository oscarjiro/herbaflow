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

    // Section labels (Analysis Name input was removed — name is auto-generated)
    expect(screen.getByText('Plants')).toBeInTheDocument()
    expect(screen.getByText('Disease')).toBeInTheDocument()
    expect(screen.getByText('Mode')).toBeInTheDocument()
    expect(screen.getByText('Advanced Parameters')).toBeInTheDocument()

    // Submit button exists and is enabled (validation runs on submit via Zod, not pre-disabled)
    const btn = screen.getByRole('button', { name: /start analysis/i })
    expect(btn).toBeEnabled()
  })

  it('submit button is enabled before submission (Zod validates on submit)', () => {
    render(<SetupPage />, { wrapper })
    const btn = screen.getByRole('button', { name: /start analysis/i })
    // Button is always enabled unless a mutation is in-flight; field errors surface on submit
    expect(btn).toBeEnabled()
  })

  it('does not render an analysis name input (name is auto-generated)', () => {
    render(<SetupPage />, { wrapper })
    // The Analysis Name field was removed from the UI — name is auto-generated server-side
    expect(screen.queryByPlaceholderText('Enter analysis name')).not.toBeInTheDocument()
    expect(screen.queryByText('Analysis Name')).not.toBeInTheDocument()
  })

  it('mode toggle defaults to guided (not auto)', () => {
    render(<SetupPage />, { wrapper })
    // ModeToggle renders two buttons: "Guided" and "Auto".
    // The active button receives the bg-hf-fg1 class; the inactive one does not.
    // This pins the initial mode state to 'guided' so any accidental change to 'auto' is caught.
    const guidedBtn = screen.getByRole('button', { name: /guided/i })
    const autoBtn = screen.getByRole('button', { name: /auto/i })
    expect(guidedBtn.className).toContain('bg-hf-fg1')
    expect(autoBtn.className).not.toContain('bg-hf-fg1')
  })
})
