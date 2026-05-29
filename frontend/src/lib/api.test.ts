/**
 * Unit tests for the typed fetch wrapper in api.ts.
 *
 * Focus: void endpoints (approve / reject / delete) return 204 No Content with
 * an empty body. Calling res.json() on an empty body throws a SyntaxError, so
 * `request` must tolerate empty responses and resolve rather than reject.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { api } from './api'

function mockFetchOnce(response: Response) {
  vi.stubGlobal('fetch', vi.fn(async () => response))
}

afterEach(() => {
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

describe('api void endpoints with empty/204 bodies', () => {
  it('rejectStage resolves on a 204 No Content response (no JSON parse error)', async () => {
    mockFetchOnce(new Response(null, { status: 204 }))
    await expect(api.rejectStage('a1')).resolves.toBeUndefined()
  })

  it('deleteAnalysis resolves on a 204 No Content response', async () => {
    mockFetchOnce(new Response(null, { status: 204 }))
    await expect(api.deleteAnalysis('a1')).resolves.toBeUndefined()
  })

  it('approveStage resolves on a 200 with an empty body', async () => {
    mockFetchOnce(new Response('', { status: 200 }))
    await expect(api.approveStage('a1')).resolves.toBeUndefined()
  })

  it('still parses a JSON body when one is present', async () => {
    mockFetchOnce(
      new Response(JSON.stringify({ analysis_id: 'a1' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    )
    await expect(
      api.createAnalysis({
        name: 'n',
        mode: 'guided',
        plant_ids: [],
        disease_ids: [],
        parameters: {},
      }),
    ).resolves.toEqual({ analysis_id: 'a1' })
  })

  it('throws a descriptive error on a non-2xx response', async () => {
    mockFetchOnce(new Response('boom', { status: 500 }))
    await expect(api.rejectStage('a1')).rejects.toThrow('API 500: boom')
  })
})
