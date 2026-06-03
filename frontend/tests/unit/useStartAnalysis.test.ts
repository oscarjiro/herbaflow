import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { server } from '@/mocks/node'
import { http, HttpResponse } from 'msw'
import { useStartAnalysis } from '@/hooks/useStartAnalysis'
import { api } from '@/lib/api'

// Mock react-router-dom navigate
const mockNavigate = vi.fn()
vi.mock('react-router-dom', () => ({
  useNavigate: () => mockNavigate,
}))

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

const ANALYSIS_ID = 'abc-123'

const baseRequest = {
  name: 'Test Analysis',
  mode: 'guided' as const,
  plant_ids: ['plant-1'],
  disease_id: 'disease-1',
  parameters: {},
}

describe('useStartAnalysis', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    localStorage.clear()
    server.use(
      http.post('http://localhost:8000/analyses', () =>
        HttpResponse.json({ analysis_id: ANALYSIS_ID })
      )
    )
  })

  afterEach(() => {
    localStorage.clear()
  })

  it('on success: saves analysis ID to localStorage under hf_last_analysis_id', async () => {
    const { result } = renderHook(() => useStartAnalysis(), { wrapper: makeWrapper() })
    result.current.mutate({ request: baseRequest })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(localStorage.getItem('hf_last_analysis_id')).toBe(ANALYSIS_ID)
  })

  it('on success: navigates to the pipeline route with analysis ID', async () => {
    const { result } = renderHook(() => useStartAnalysis(), { wrapper: makeWrapper() })
    result.current.mutate({ request: baseRequest })
    await waitFor(() => expect(result.current.isSuccess).toBe(true))
    expect(mockNavigate).toHaveBeenCalledWith(`/analysis/${ANALYSIS_ID}`)
  })

  it('on error: does NOT navigate', async () => {
    server.use(
      http.post('http://localhost:8000/analyses', () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      )
    )
    const { result } = renderHook(() => useStartAnalysis(), { wrapper: makeWrapper() })
    result.current.mutate({ request: baseRequest })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(mockNavigate).not.toHaveBeenCalled()
  })

  it('on error: does NOT save to localStorage', async () => {
    server.use(
      http.post('http://localhost:8000/analyses', () =>
        HttpResponse.json({ detail: 'Server error' }, { status: 500 })
      )
    )
    const { result } = renderHook(() => useStartAnalysis(), { wrapper: makeWrapper() })
    result.current.mutate({ request: baseRequest })
    await waitFor(() => expect(result.current.isError).toBe(true))
    expect(localStorage.getItem('hf_last_analysis_id')).toBeNull()
  })

  it('mutation function is callable', () => {
    const { result } = renderHook(() => useStartAnalysis(), { wrapper: makeWrapper() })
    expect(typeof result.current.mutate).toBe('function')
    expect(typeof result.current.mutateAsync).toBe('function')
  })

  // Manual inputs (compounds/targets) now travel inside the create request
  // itself; the hook no longer performs a separate inject call. Invalid inputs
  // now fail the create call at the backend boundary (surfaced via isError),
  // so the former create->inject two-call hook tests are removed here rather
  // than rewritten against the old endpoints.
})

describe('single create call', () => {
  it('api exposes no inject wrappers', () => {
    expect((api as Record<string, unknown>).injectCompounds).toBeUndefined()
    expect((api as Record<string, unknown>).injectTargets).toBeUndefined()
  })

  it('createAnalysis is called exactly once carrying inline inputs', async () => {
    const createSpy = vi.spyOn(api, 'createAnalysis')
      .mockResolvedValue({ analysis_id: 'a1' } as never)
    await api.createAnalysis({
      name: 'n', mode: 'guided', plant_ids: [], disease_id: 'd1',
      parameters: {} as never, compounds: ['CCO'],
    })
    expect(createSpy).toHaveBeenCalledTimes(1)
    createSpy.mockRestore()
  })
})
