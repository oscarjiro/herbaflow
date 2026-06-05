/**
 * Setup validate-before-commit review flow.
 *
 * In a manual mode, clicking Start Analysis runs a (non-mutating) validation pass
 * and shows a ValidationReview card. Clicking Continue triggers the real create
 * mutation. A single manual scope uses the chunked `validateInChunks` path; two
 * or more scopes use the combined `validateScopes` pass (shared target union).
 * Standard mode is covered elsewhere and must keep submitting directly.
 */
// jsdom shims required by the Radix/cmdk disease combobox.
Element.prototype.hasPointerCapture = vi.fn() as unknown as typeof Element.prototype.hasPointerCapture
Element.prototype.scrollIntoView = vi.fn()
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api } from '@/lib/api'

// A single disease so the selector can satisfy Zod in the single-scope test.
vi.mock('@/hooks/useDiseases', () => ({
  useDiseases: () => ({
    data: [
      {
        disease_id: 'd1',
        disease_name: 'type 2 diabetes mellitus',
        ontology_id: 'DOID_2843',
        ontology_source: 'DOID',
        disease_aliases: [],
        target_count: 5,
      },
    ],
    isLoading: false,
  }),
}))

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

async function renderSetupPage() {
  const { default: SetupPage } = await import('@/pages/SetupPage')
  const queryClient = makeQueryClient()
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <SetupPage />
      </MemoryRouter>
    </QueryClientProvider>,
  )
}

const cannedPayload = {
  valid: [{ id: 1 }, { id: 2 }],
  failed: [],
  normalized: [],
  duplicates: [],
  reused: 0,
  enriched: 2,
}

beforeEach(() => {
  localStorage.clear()
  // Mount cache-restore check resolves to "not found" so we stay on the setup page.
  vi.spyOn(api, 'getAnalysisStatus').mockRejectedValue(new Error('not found'))
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('SetupPage — validate-before-commit review', () => {
  it('single scope: reviews via validateInChunks, then Continue sends the resolved accessions', async () => {
    const resolved = {
      ...cannedPayload,
      valid: [
        { gene_symbol: 'TP53', uniprot_id: 'P04637' },
        { gene_symbol: 'EGFR', uniprot_id: 'P00533' },
      ],
    }
    const validateSpy = vi.spyOn(api, 'validateInChunks').mockResolvedValue(resolved as never)
    const createSpy = vi.spyOn(api, 'createAnalysis').mockResolvedValue({ analysis_id: 'a1' })

    await renderSetupPage()

    // Manual compound targets (plant side); disease is SELECTED (one manual scope).
    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))
    fireEvent.change(screen.getByLabelText('Targets'), { target: { value: 'TP53\nEGFR' } })
    await userEvent.click(screen.getByRole('combobox'))
    await userEvent.click(screen.getByText('DOID:2843'))

    fireEvent.click(screen.getByRole('button', { name: /start analysis/i }))

    await screen.findByTestId('validation-review')
    // One manual scope → chunked path, raw typed symbols.
    expect(validateSpy).toHaveBeenCalledWith('target', ['TP53', 'EGFR'], false, expect.any(Function))
    expect(createSpy).not.toHaveBeenCalled()

    await userEvent.click(screen.getByRole('button', { name: /continue \(2\)/i }))
    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(1))
    const req = createSpy.mock.calls[0][0]
    expect(req.targets).toEqual(['P04637', 'P00533'])
  })

  it('two scopes: one combined pass, then Continue reuses each scope’s accessions', async () => {
    const byScope = {
      targets: {
        ...cannedPayload,
        valid: [
          { gene_symbol: 'TP53', uniprot_id: 'P04637' },
          { gene_symbol: 'EGFR', uniprot_id: 'P00533' },
        ],
      },
      disease_targets: {
        ...cannedPayload,
        valid: [{ gene_symbol: 'TP53', uniprot_id: 'P04637' }],
      },
    }
    const validateSpy = vi.spyOn(api, 'validateScopes').mockResolvedValue(byScope as never)
    const createSpy = vi.spyOn(api, 'createAnalysis').mockResolvedValue({ analysis_id: 'a1' })

    await renderSetupPage()

    // Manual compound targets AND manual disease targets → two scopes.
    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))
    fireEvent.change(screen.getByLabelText('Targets'), { target: { value: 'TP53\nEGFR' } })
    fireEvent.click(screen.getByTestId('disease-input-mode-manual'))
    fireEvent.change(screen.getByLabelText('Disease targets'), { target: { value: 'TP53' } })

    fireEvent.click(screen.getByRole('button', { name: /start analysis/i }))

    await screen.findByTestId('validation-review')
    // Both scopes validated together in one combined pass.
    expect(validateSpy).toHaveBeenCalledWith([
      { scope: 'targets', inputs: ['TP53', 'EGFR'], lenient: false },
      { scope: 'disease_targets', inputs: ['TP53'], lenient: false },
    ])
    expect(screen.getByText('Compound targets')).toBeInTheDocument()
    expect(screen.getByText('Disease targets')).toBeInTheDocument()
    expect(createSpy).not.toHaveBeenCalled()

    // Combined ready count is 2 + 1 = 3; create reuses each scope's accessions.
    await userEvent.click(screen.getByRole('button', { name: /continue \(3\)/i }))
    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(1))
    const req = createSpy.mock.calls[0][0]
    expect(req.targets).toEqual(['P04637', 'P00533'])
    expect(req.manual_disease_targets).toEqual(['P04637'])
  })

  it('Go back returns to editing without creating a run', async () => {
    vi.spyOn(api, 'validateScopes').mockResolvedValue({
      targets: cannedPayload,
      disease_targets: cannedPayload,
    } as never)
    const createSpy = vi.spyOn(api, 'createAnalysis').mockResolvedValue({ analysis_id: 'a1' })

    await renderSetupPage()
    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))
    fireEvent.change(screen.getByLabelText('Targets'), { target: { value: 'TP53' } })
    fireEvent.click(screen.getByTestId('disease-input-mode-manual'))
    fireEvent.change(screen.getByLabelText('Disease targets'), { target: { value: 'TP53' } })
    fireEvent.click(screen.getByRole('button', { name: /start analysis/i }))

    await screen.findByTestId('validation-review')
    await userEvent.click(screen.getByRole('button', { name: /go back/i }))

    await waitFor(() =>
      expect(screen.queryByTestId('validation-review')).not.toBeInTheDocument(),
    )
    expect(screen.getByLabelText('Targets')).toBeInTheDocument()
    expect(createSpy).not.toHaveBeenCalled()
  })

  it('surfaces a validation error (e.g. 503) and stays on the form', async () => {
    vi.spyOn(api, 'validateScopes').mockRejectedValue(
      new Error('The service is temporarily unavailable — please try again.'),
    )
    const createSpy = vi.spyOn(api, 'createAnalysis')

    await renderSetupPage()
    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))
    fireEvent.change(screen.getByLabelText('Targets'), { target: { value: 'TP53' } })
    fireEvent.click(screen.getByTestId('disease-input-mode-manual'))
    fireEvent.change(screen.getByLabelText('Disease targets'), { target: { value: 'TP53' } })
    fireEvent.click(screen.getByRole('button', { name: /start analysis/i }))

    expect(await screen.findByText(/temporarily unavailable/i)).toBeInTheDocument()
    expect(screen.queryByTestId('validation-review')).not.toBeInTheDocument()
    expect(createSpy).not.toHaveBeenCalled()
  })
})
