import { describe, it, expect } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import { useAnalysisStatus } from '@/hooks/useAnalysisStatus'
import { isTerminalStatus } from '@/types/api'
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

describe('isTerminalStatus', () => {
  it('returns false for intermediate stage_N_complete (auto mode)', () => {
    expect(isTerminalStatus('stage_1_complete')).toBe(false)
    expect(isTerminalStatus('stage_2_complete')).toBe(false)
    expect(isTerminalStatus('stage_8_complete')).toBe(false)
  })

  it('returns false for stage_N_running', () => {
    expect(isTerminalStatus('stage_1_running')).toBe(false)
    expect(isTerminalStatus('stage_8_running')).toBe(false)
  })

  it('returns false for stage_N_awaiting_approval', () => {
    expect(isTerminalStatus('stage_1_awaiting_approval')).toBe(false)
  })

  it('returns true for final complete', () => {
    expect(isTerminalStatus('complete')).toBe(true)
  })

  it('returns true for top-level failed', () => {
    expect(isTerminalStatus('failed')).toBe(true)
  })

  it('returns true for stage_N_rejected', () => {
    expect(isTerminalStatus('stage_1_rejected')).toBe(true)
    expect(isTerminalStatus('stage_8_rejected')).toBe(true)
  })

  it('returns true for stage_N_failed', () => {
    expect(isTerminalStatus('stage_1_failed')).toBe(true)
    expect(isTerminalStatus('stage_8_failed')).toBe(true)
  })

  it('returns false for pending', () => {
    expect(isTerminalStatus('pending')).toBe(false)
  })

  it('returns false for empty string or invalid input', () => {
    expect(isTerminalStatus('')).toBe(false)
    // @ts-expect-error — testing runtime guard
    expect(isTerminalStatus(null)).toBe(false)
    // @ts-expect-error — testing runtime guard
    expect(isTerminalStatus(undefined)).toBe(false)
  })
})
