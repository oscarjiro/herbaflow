import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { http, HttpResponse } from 'msw'
import { server } from '@/mocks/node'
import { statusFixture, analysisFixture } from '@/mocks/data'
import PipelinePage from '@/pages/PipelinePage'

// ============================================================================
// Test wrapper — MemoryRouter with route param
// ============================================================================

function wrapper({ children }: { children: React.ReactNode }) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return (
    <QueryClientProvider client={qc}>
      <MemoryRouter initialEntries={['/analysis/test-id-1']}>
        <Routes>
          <Route path="analysis/:id" element={children} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  )
}

// ============================================================================
// Tests
// ============================================================================

describe('PipelinePage — guided mode, stage 3 awaiting approval', () => {
  beforeEach(() => {
    // Override handlers to return guided mode fixture with awaiting_approval
    server.use(
      http.get('http://localhost:8000/analyses/test-id-1/status', () =>
        HttpResponse.json({
          ...statusFixture,
          mode: 'guided',
          status: 'stage_3_awaiting_approval',
          current_stage: 3,
          progress: {},
          created_at: null,
          updated_at: null,
        }),
      ),
      http.get('http://localhost:8000/analyses/test-id-1', () =>
        HttpResponse.json({
          ...analysisFixture,
          mode: 'guided',
          status: 'stage_3_awaiting_approval',
          current_stage: 3,
          completed_at: null,
        }),
      ),
    )
  })

  it('renders ApprovalBar with "Approve & Continue" button', async () => {
    render(<PipelinePage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /approve & continue/i })).toBeInTheDocument()
    })
  })

  it('calls POST /analyses/test-id-1/approve when "Approve & Continue" is clicked', async () => {
    const user = userEvent.setup()

    let approveCalled = false
    server.use(
      http.post('http://localhost:8000/analyses/test-id-1/approve', () => {
        approveCalled = true
        return new HttpResponse(null, { status: 200 })
      }),
    )

    render(<PipelinePage />, { wrapper })

    const approveBtn = await screen.findByRole('button', { name: /approve & continue/i })
    await user.click(approveBtn)

    await waitFor(() => {
      expect(approveCalled).toBe(true)
    })
  })
})
