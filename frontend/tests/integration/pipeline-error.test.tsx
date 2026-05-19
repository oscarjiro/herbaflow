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

describe('PipelinePage — failed status', () => {
  beforeEach(() => {
    server.use(
      http.get('http://localhost:8000/analyses/test-id-1/status', () =>
        HttpResponse.json({
          ...statusFixture,
          mode: 'guided',
          status: 'failed',
          current_stage: 3,
          error_message: 'Stage 3 failed: API timeout',
          progress: {},
          created_at: null,
          updated_at: null,
        }),
      ),
      http.get('http://localhost:8000/analyses/test-id-1', () =>
        HttpResponse.json({
          ...analysisFixture,
          status: 'failed',
          error_message: 'Stage 3 failed: API timeout',
          completed_at: null,
        }),
      ),
    )
  })

  it('shows "Analysis failed" error state', async () => {
    render(<PipelinePage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Analysis failed')).toBeInTheDocument()
    })
  })

  it('shows "Start New Analysis" button', async () => {
    render(<PipelinePage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByRole('button', { name: /start new analysis/i })).toBeInTheDocument()
    })
  })

  it('shows the error message text', async () => {
    render(<PipelinePage />, { wrapper })

    await waitFor(() => {
      expect(screen.getByText('Stage 3 failed: API timeout')).toBeInTheDocument()
    })
  })
})
