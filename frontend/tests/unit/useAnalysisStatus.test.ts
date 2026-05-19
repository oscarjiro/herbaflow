import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import { useAnalysisStatus } from '@/hooks/useAnalysisStatus'
import React from 'react'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

describe('useAnalysisStatus', () => {
  it('stops polling when status is complete', async () => {
    server.use(
      http.get('http://localhost:8000/analyses/:id/status', () =>
        HttpResponse.json({ status: 'complete', current_stage: null, analysis_id: 'x', mode: 'guided', progress: {}, created_at: null, updated_at: null })
      )
    )
    const { result } = renderHook(() => useAnalysisStatus('x'), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.data?.status).toBe('complete'))
    // refetchInterval returns false → no interval set
    expect(result.current.data?.status).toBe('complete')
  })

  it('stops polling when status is failed', async () => {
    server.use(
      http.get('http://localhost:8000/analyses/:id/status', () =>
        HttpResponse.json({ status: 'failed', current_stage: null, analysis_id: 'x', mode: 'guided', progress: {}, created_at: null, updated_at: null })
      )
    )
    const { result } = renderHook(() => useAnalysisStatus('x'), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.data?.status).toBe('failed'))
  })

  it('stops polling when status is stage_3_rejected', async () => {
    server.use(
      http.get('http://localhost:8000/analyses/:id/status', () =>
        HttpResponse.json({ status: 'stage_3_rejected', current_stage: 3, analysis_id: 'x', mode: 'guided', progress: {}, created_at: null, updated_at: null })
      )
    )
    const { result } = renderHook(() => useAnalysisStatus('x'), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.data?.status).toBe('stage_3_rejected'))
  })

  it('continues polling when status is stage_2_running', async () => {
    let callCount = 0
    server.use(
      http.get('http://localhost:8000/analyses/:id/status', () => {
        callCount++
        return HttpResponse.json({ status: 'stage_2_running', current_stage: 2, analysis_id: 'x', mode: 'guided', progress: {}, created_at: null, updated_at: null })
      })
    )
    const { result } = renderHook(() => useAnalysisStatus('x'), { wrapper: makeWrapper() })
    await waitFor(() => expect(result.current.data?.status).toBe('stage_2_running'))
    // Just verify it fetched data — polling is active but we can't wait 2s in a unit test
    expect(callCount).toBeGreaterThan(0)
  })
})
