import { render, screen, waitFor } from '@testing-library/react'
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

describe('PipelinePage — auto mode, complete status', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost:8000/analyses/test-id-1/status', () =>
        HttpResponse.json({
          ...statusFixture,
          mode: 'auto',
          status: 'complete',
          current_stage: 8,
          progress: {},
          created_at: null,
          updated_at: null,
        }),
      ),
      http.get('http://localhost:8000/analyses/test-id-1', () =>
        HttpResponse.json({
          ...analysisFixture,
          mode: 'auto',
          status: 'complete',
          current_stage: 8,
          completed_at: null,
        }),
      ),
    )
  })

  it('does not render the ApprovalBar in auto mode', async () => {
    render(<PipelinePage />, { wrapper })

    // Wait for data to load (stage 8 panel should appear)
    await waitFor(() => {
      expect(screen.getByText(/stage 8/i)).toBeInTheDocument()
    })

    // ApprovalBar must not be present
    expect(screen.queryByRole('button', { name: /approve & continue/i })).not.toBeInTheDocument()
  })
})
