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

    // Initially no textarea
    expect(screen.queryByTestId('compounds-textarea')).not.toBeInTheDocument()

    // Click "Manual compounds" toggle button
    const manualBtn = screen.getByTestId('input-mode-manual')
    fireEvent.click(manualBtn)

    // Textarea should now be visible
    expect(screen.getByTestId('compounds-textarea')).toBeInTheDocument()
    expect(
      screen.getByPlaceholderText('Enter SMILES or InChI strings, one per line')
    ).toBeInTheDocument()
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

    // Textarea is empty → button must be disabled
    expect(submitBtn).toBeDisabled()

    // Type a SMILES string → button should become enabled (diseases still empty,
    // so it will still be disabled — this verifies the compound guard specifically
    // by checking that the textarea value is reflected)
    fireEvent.change(screen.getByTestId('compounds-textarea'), {
      target: { value: 'CC(=O)Oc1ccccc1C(=O)O' },
    })

    // Still disabled because no disease selected, but the structure count hint appears
    expect(screen.getByText(/1 structure entered/i)).toBeInTheDocument()
  })
})

// ---------------------------------------------------------------------------
// Test 4: isSkippedStage correctly handles stage_1 skipped result
// ---------------------------------------------------------------------------

describe('isSkippedStage type guard', () => {
  it('returns true for a stage_1 skipped sentinel object', () => {
    const skippedResult = { status: 'skipped', input_mode: 'manual_compounds' }
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
