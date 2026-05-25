/**
 * Unit tests for T4.4 — Manual Target Input
 *
 * Tests:
 * 1. Targets textarea renders when mode = manual_targets
 * 2. Plants section hidden when mode = manual_targets
 * 3. Submit button disabled when targets textarea is empty
 * 4. Third mode option (manual_targets) exists in toggle
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

/**
 * Render SetupPage inside all required providers.
 * We use MemoryRouter so useNavigate doesn't throw.
 * MSW server handles /analyses status check on mount.
 */
async function renderSetupPage() {
  const { default: SetupPage } = await import('@/pages/SetupPage')
  const queryClient = makeQueryClient()
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SetupPage />
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// ---------------------------------------------------------------------------
// Test 1: Targets textarea renders when input mode = manual_targets
// ---------------------------------------------------------------------------

describe('SetupPage — manual target input mode', () => {
  it('shows targets textarea after switching to manual_targets mode', async () => {
    await renderSetupPage()

    // Initially no targets textarea
    expect(screen.queryByTestId('targets-textarea')).not.toBeInTheDocument()

    // Click "Manual targets" toggle button
    const manualTargetsBtn = screen.getByTestId('input-mode-manual-targets')
    fireEvent.click(manualTargetsBtn)

    // Targets textarea should now be visible
    expect(screen.getByTestId('targets-textarea')).toBeInTheDocument()
    expect(
      screen.getByPlaceholderText('Enter gene symbols or UniProt accessions, one per line')
    ).toBeInTheDocument()
  })

  // ---------------------------------------------------------------------------
  // Test 2: Plants section hidden when mode = manual_targets
  // ---------------------------------------------------------------------------

  it('hides plants section when manual_targets mode is active', async () => {
    await renderSetupPage()

    // Plants section visible by default
    expect(screen.getByTestId('plants-section')).toBeInTheDocument()

    // Switch to manual targets mode
    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))

    // Plants section must be gone
    expect(screen.queryByTestId('plants-section')).not.toBeInTheDocument()
  })

  // ---------------------------------------------------------------------------
  // Test 3: Submit button disabled when targets textarea is empty
  // ---------------------------------------------------------------------------

  it('disables submit button when manual_targets mode is active but textarea is empty', async () => {
    await renderSetupPage()

    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))

    const submitBtn = screen.getByRole('button', { name: /start analysis/i })

    // Textarea is empty → button must be disabled
    expect(submitBtn).toBeDisabled()

    // Type a gene symbol → structure count hint appears
    fireEvent.change(screen.getByTestId('targets-textarea'), {
      target: { value: 'TP53' },
    })

    // Still disabled because no disease selected, but count hint should appear
    expect(screen.getByText(/1 target entered/i)).toBeInTheDocument()
  })

  // ---------------------------------------------------------------------------
  // Test 4: Third mode option (manual_targets) exists in the toggle
  // ---------------------------------------------------------------------------

  it('renders a manual_targets toggle button', async () => {
    await renderSetupPage()

    const manualTargetsBtn = screen.getByTestId('input-mode-manual-targets')
    expect(manualTargetsBtn).toBeInTheDocument()
    expect(manualTargetsBtn).toHaveTextContent(/manual targets/i)
  })
})
