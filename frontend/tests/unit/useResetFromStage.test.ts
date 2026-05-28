import { describe, it, expect, vi } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import { useResetFromStage } from '@/hooks/useResetFromStage'

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return {
    qc,
    wrapper: ({ children }: { children: React.ReactNode }) =>
      React.createElement(QueryClientProvider, { client: qc }, children),
  }
}

const ANALYSIS_ID = 'test-analysis-id'

const mockStatus = {
  analysis_id: ANALYSIS_ID,
  status: 'stage_5_running',
  mode: 'guided',
  current_stage: 5,
  progress: {},
  created_at: null,
  updated_at: null,
  error_message: null,
  expires_at: null,
}

describe('useResetFromStage', () => {
  it('mutation calls the correct API endpoint with stage number and analysis ID', async () => {
    let capturedUrl: string | null = null
    server.use(
      http.post(`http://localhost:8000/analyses/${ANALYSIS_ID}/reset-from/:stage`, ({ request }) => {
        capturedUrl = request.url
        return HttpResponse.json(mockStatus)
      })
    )
    const { qc, wrapper } = makeWrapper()
    const { result } = renderHook(() => useResetFromStage(ANALYSIS_ID), { wrapper })
    result.current.mutate({ stage: 5 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(capturedUrl).toContain(`/analyses/${ANALYSIS_ID}/reset-from/5`)
    qc.clear()
  })

  it('calls reset-from with stage 3 and body', async () => {
    let capturedBody: unknown = null
    server.use(
      http.post(`http://localhost:8000/analyses/${ANALYSIS_ID}/reset-from/:stage`, async ({ request }) => {
        capturedBody = await request.json().catch(() => null)
        return HttpResponse.json(mockStatus)
      })
    )
    const { qc, wrapper } = makeWrapper()
    const { result } = renderHook(() => useResetFromStage(ANALYSIS_ID), { wrapper })
    result.current.mutate({ stage: 3, body: { rerun: true } })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(capturedBody).toEqual({ rerun: true })
    qc.clear()
  })

  it('on success: invalidates the analysis query', async () => {
    server.use(
      http.post(`http://localhost:8000/analyses/${ANALYSIS_ID}/reset-from/:stage`, () =>
        HttpResponse.json(mockStatus)
      )
    )
    const { qc, wrapper } = makeWrapper()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useResetFromStage(ANALYSIS_ID), { wrapper })
    result.current.mutate({ stage: 5 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['analysis', ANALYSIS_ID] })
    )
    qc.clear()
  })

  it('on success: invalidates the analysisStatus query', async () => {
    server.use(
      http.post(`http://localhost:8000/analyses/${ANALYSIS_ID}/reset-from/:stage`, () =>
        HttpResponse.json(mockStatus)
      )
    )
    const { qc, wrapper } = makeWrapper()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useResetFromStage(ANALYSIS_ID), { wrapper })
    result.current.mutate({ stage: 5 })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(invalidateSpy).toHaveBeenCalledWith(
      expect.objectContaining({ queryKey: ['analysisStatus', ANALYSIS_ID] })
    )
    qc.clear()
  })

  it('on error: does NOT invalidate query', async () => {
    server.use(
      http.post(`http://localhost:8000/analyses/${ANALYSIS_ID}/reset-from/:stage`, () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      )
    )
    const { qc, wrapper } = makeWrapper()
    const invalidateSpy = vi.spyOn(qc, 'invalidateQueries')
    const { result } = renderHook(() => useResetFromStage(ANALYSIS_ID), { wrapper })
    result.current.mutate({ stage: 5 })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(invalidateSpy).not.toHaveBeenCalled()
    qc.clear()
  })

  it('mutation function is callable', () => {
    const { wrapper } = makeWrapper()
    const { result } = renderHook(() => useResetFromStage(ANALYSIS_ID), { wrapper })
    expect(typeof result.current.mutate).toBe('function')
    expect(typeof result.current.mutateAsync).toBe('function')
  })
})
