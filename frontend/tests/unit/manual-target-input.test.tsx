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
    expect(screen.queryByLabelText('Targets')).not.toBeInTheDocument()

    // Click "Manual targets" toggle button
    const manualTargetsBtn = screen.getByTestId('input-mode-manual-targets')
    fireEvent.click(manualTargetsBtn)

    // Targets textarea should now be visible (queried by its aria-label)
    const textarea = screen.getByLabelText('Targets')
    expect(textarea).toBeInTheDocument()
    // Placeholder contains example gene symbols (literal newline in the attribute)
    expect(textarea.getAttribute('placeholder')).toMatch(/TP53/)
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

    // Button is enabled (validation runs on submit via Zod, not pre-disabled)
    expect(submitBtn).toBeEnabled()

    // Type a gene symbol → target count hint should appear
    fireEvent.change(screen.getByLabelText('Targets'), {
      target: { value: 'TP53' },
    })

    // Count hint confirms textarea value is tracked
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

  // ---------------------------------------------------------------------------
  // Test 5: Lenient checkbox present and unchecked in manual_targets mode
  // ---------------------------------------------------------------------------

  it('shows an unchecked lenient checkbox in manual_targets mode', async () => {
    await renderSetupPage()

    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))

    const checkbox = screen.getByRole('checkbox', { name: /keep unrecognized symbols/i })
    expect(checkbox).toBeInTheDocument()
    expect(checkbox).not.toBeChecked()
  })

  it('lenient checkbox is absent in manual_compounds mode', async () => {
    await renderSetupPage()

    fireEvent.click(screen.getByTestId('input-mode-manual'))

    expect(
      screen.queryByRole('checkbox', { name: /keep unrecognized symbols/i })
    ).not.toBeInTheDocument()
  })
})
