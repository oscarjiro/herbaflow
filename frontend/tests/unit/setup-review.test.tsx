/**
 * Setup validate-before-commit review flow.
 *
 * In a manual mode, clicking Start Analysis runs a (non-mutating) validation pass
 * and shows a ValidationReview card. Clicking Continue triggers the real create
 * mutation. Standard mode is covered elsewhere and must keep submitting directly.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { api } from '@/lib/api'

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

describe('SetupPage — validate-before-commit review (manual mode)', () => {
  it('shows the review after Start, then Continue sends the dry-run resolved accessions (not raw symbols)', async () => {
    // The dry-run resolved+persisted these targets; its valid dicts carry the
    // canonical UniProt accessions. Continue must reuse those (DB cache hits) —
    // NOT the raw typed gene symbols.
    const resolvedPayload = {
      ...cannedPayload,
      valid: [
        { gene_symbol: 'TP53', uniprot_id: 'P04637' },
        { gene_symbol: 'EGFR', uniprot_id: 'P00533' },
      ],
    }
    const validateSpy = vi
      .spyOn(api, 'validateInChunks')
      .mockResolvedValue(resolvedPayload as never)
    const createSpy = vi
      .spyOn(api, 'createAnalysis')
      .mockResolvedValue({ analysis_id: 'a1' })

    await renderSetupPage()

    // Switch to manual_targets and enter two targets.
    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))
    fireEvent.change(screen.getByLabelText('Targets'), {
      target: { value: 'TP53\nEGFR' },
    })
    // Provide manual disease targets so Zod passes without a disease selection.
    // Precedence still reviews the compound-target input first.
    fireEvent.click(screen.getByTestId('disease-input-mode-manual'))
    fireEvent.change(screen.getByLabelText('Disease targets'), {
      target: { value: 'TP53' },
    })

    // Start → validation runs against the RAW typed symbols, review appears.
    fireEvent.click(screen.getByRole('button', { name: /start analysis/i }))

    await screen.findByTestId('validation-review')
    expect(screen.getByText(/2 ready/i)).toBeInTheDocument()
    expect(validateSpy).toHaveBeenCalledWith(
      'target',
      ['TP53', 'EGFR'],
      false,
      expect.any(Function),
    )
    // The create mutation has NOT fired yet — review gates it.
    expect(createSpy).not.toHaveBeenCalled()

    // Continue → create mutation fires with the resolved canonical accessions.
    await userEvent.click(screen.getByRole('button', { name: /continue \(2\)/i }))
    await waitFor(() => expect(createSpy).toHaveBeenCalledTimes(1))
    const req = createSpy.mock.calls[0][0]
    expect(req.targets).toEqual(['P04637', 'P00533'])
  })

  it('Go back returns to editing without creating a run', async () => {
    vi.spyOn(api, 'validateInChunks').mockResolvedValue(cannedPayload as never)
    const createSpy = vi
      .spyOn(api, 'createAnalysis')
      .mockResolvedValue({ analysis_id: 'a1' })

    await renderSetupPage()
    fireEvent.click(screen.getByTestId('input-mode-manual-targets'))
    fireEvent.change(screen.getByLabelText('Targets'), { target: { value: 'TP53' } })
    fireEvent.click(screen.getByTestId('disease-input-mode-manual'))
    fireEvent.change(screen.getByLabelText('Disease targets'), { target: { value: 'TP53' } })
    fireEvent.click(screen.getByRole('button', { name: /start analysis/i }))

    await screen.findByTestId('validation-review')
    await userEvent.click(screen.getByRole('button', { name: /go back/i }))

    // Review gone, back to the form, nothing created.
    await waitFor(() =>
      expect(screen.queryByTestId('validation-review')).not.toBeInTheDocument(),
    )
    expect(screen.getByLabelText('Targets')).toBeInTheDocument()
    expect(createSpy).not.toHaveBeenCalled()
  })

  it('surfaces a validation error (e.g. 503) and stays on the form', async () => {
    vi.spyOn(api, 'validateInChunks').mockRejectedValue(
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
