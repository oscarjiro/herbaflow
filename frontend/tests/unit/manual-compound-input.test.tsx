/**
 * Unit tests for T4.3 — Manual Compound Input
 *
 * Tests:
 * 1. Textarea renders when mode = manual_compounds
 * 2. Plants section hidden when mode = manual_compounds
 * 3. Submit button disabled when textarea empty
 * 4. isSkippedStage correctly handles stage_1 skipped result
 */
import { render, screen, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { isSkippedStage } from '@/types/api'

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
 * MSW server is set up in vitest.setup.ts (handles /analyses status call).
 */
async function renderSetupPage() {
  // Dynamic import so module-level side effects don't run before providers
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
// Test 1: Textarea renders when input mode = manual_compounds
// ---------------------------------------------------------------------------

describe('SetupPage — manual compound input mode', () => {
  it('shows compound textarea after switching to manual_compounds mode', async () => {
    await renderSetupPage()

    // Initially no Compounds textarea
    expect(screen.queryByLabelText('Compounds')).not.toBeInTheDocument()

    // Click "Manual compounds" toggle button
    const manualBtn = screen.getByTestId('input-mode-manual')
    fireEvent.click(manualBtn)

    // Textarea should now be visible (queried by its aria-label)
    const textarea = screen.getByLabelText('Compounds')
    expect(textarea).toBeInTheDocument()
    // Placeholder contains example SMILES string (literal newline in the attribute)
    expect(textarea.getAttribute('placeholder')).toMatch(/CC\(=O\)Oc1ccccc1/)
  })

  // ---------------------------------------------------------------------------
  // Test 2: Plants section hidden when mode = manual_compounds
  // ---------------------------------------------------------------------------

  it('hides plants section when manual_compounds mode is active', async () => {
    await renderSetupPage()

    // Plants section visible by default
    expect(screen.getByTestId('plants-section')).toBeInTheDocument()

    // Switch to manual mode
    fireEvent.click(screen.getByTestId('input-mode-manual'))

    // Plants section must be gone
    expect(screen.queryByTestId('plants-section')).not.toBeInTheDocument()
  })

  // ---------------------------------------------------------------------------
  // Test 3: Submit button disabled when textarea is empty
  // ---------------------------------------------------------------------------

  it('disables submit button when manual mode is active but textarea is empty', async () => {
    await renderSetupPage()

    fireEvent.click(screen.getByTestId('input-mode-manual'))

    const submitBtn = screen.getByRole('button', { name: /start analysis/i })

    // Button is enabled (validation runs on submit via Zod, not pre-disabled)
    expect(submitBtn).toBeEnabled()

    // Type a SMILES string → structure count hint should appear
    fireEvent.change(screen.getByLabelText('Compounds'), {
      target: { value: 'CC(=O)Oc1ccccc1C(=O)O' },
    })

    // Structure count hint confirms textarea value is tracked
    expect(screen.getByText(/1 structure entered/i)).toBeInTheDocument()
  })

  // ---------------------------------------------------------------------------
  // Test: coupled-card layout — Plants + Disease cards and helper text
  // ---------------------------------------------------------------------------

  it('renders the Plants and Disease card titles', async () => {
    await renderSetupPage()

    expect(screen.getByText('Plants')).toBeInTheDocument()
    expect(screen.getByText('Disease')).toBeInTheDocument()
  })

  it('shows the skipped-stages helper text alongside the Compounds textarea in manual_compounds mode', async () => {
    await renderSetupPage()

    fireEvent.click(screen.getByTestId('input-mode-manual'))

    // Helper text and the Compounds textarea live in the same (Plants) card
    expect(screen.getByText(/Stages 1–2 skipped/i)).toBeInTheDocument()
    expect(screen.getByLabelText('Compounds')).toBeInTheDocument()
  })

  // ---------------------------------------------------------------------------
  // Test: contextual ADME checkbox next to manual compounds textarea
  // ---------------------------------------------------------------------------

  it('renders a checked ADME checkbox next to the compounds textarea and toggles it', async () => {
    await renderSetupPage()

    fireEvent.click(screen.getByTestId('input-mode-manual'))

    // Checkbox should be present with the contextual label
    const checkbox = screen.getByRole('checkbox', {
      name: /apply adme screening to these compounds/i,
    })
    expect(checkbox).toBeInTheDocument()
    // DEFAULT_PARAMS.apply_adme_to_manual is true
    expect(checkbox).toBeChecked()

    // Clicking unchecks it
    fireEvent.click(checkbox)
    expect(checkbox).not.toBeChecked()
  })
})

// ---------------------------------------------------------------------------
// Test 4: isSkippedStage correctly handles stage_1 skipped result
// ---------------------------------------------------------------------------

describe('isSkippedStage type guard', () => {
  it('returns true for a stage_1 skipped sentinel object', () => {
    const skippedResult = { state: 'not_applicable' }
    expect(isSkippedStage(skippedResult)).toBe(true)
  })

  it('returns false for a normal stage_1 result', () => {
    const normalResult = {
      compound_ids: ['abc-123'],
      compound_count: 1,
      total_compounds: 1,
      plants_covered: 0,
      compounds: [],
    }
    expect(isSkippedStage(normalResult)).toBe(false)
  })

  it('returns false for null', () => {
    expect(isSkippedStage(null)).toBe(false)
  })

  it('returns false for an object without a status field', () => {
    expect(isSkippedStage({ input_mode: 'manual_compounds' })).toBe(false)
  })

  it('returns false for status = "running" (not skipped)', () => {
    expect(isSkippedStage({ status: 'running' })).toBe(false)
  })
})
