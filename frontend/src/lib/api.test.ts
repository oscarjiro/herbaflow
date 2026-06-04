/**
 * Unit tests for the typed fetch wrapper in api.ts.
 *
 * Focus: void endpoints (approve / reject / delete) return 204 No Content with
 * an empty body. Calling res.json() on an empty body throws a SyntaxError, so
 * `request` must tolerate empty responses and resolve rather than reject.
 *
 * Also covers: raw string id path-args are wrapped in encodeURIComponent so a
 * hostile id can't break out of the URL path.
 *
 * Also covers: humanized error messages from request().
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { api, ApiError } from './api'

function mockFetchOnce(response: Response) {
  vi.stubGlobal('fetch', vi.fn(async () => response))
}

function lastFetchUrl(): string {
  const calls = (globalThis.fetch as any).mock.calls
  return calls[calls.length - 1][0] as string
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
        disease_id: null,
        parameters: {} as never,
      }),
    ).resolves.toEqual({ analysis_id: 'a1' })
  })

  it('throws a descriptive error on a non-2xx response with plain text body', async () => {
    // Plain-text body (not JSON) — falls through to generic fallback
    mockFetchOnce(new Response('boom', { status: 500 }))
    await expect(api.rejectStage('a1')).rejects.toThrow(/500/)
  })
})

describe('api humanized error messages', () => {
  it('422 with Pydantic detail array joins .msg fields', async () => {
    const body = JSON.stringify({
      detail: [
        { msg: 'field required', loc: ['body', 'x'], type: 'missing' },
        { msg: 'too short' },
      ],
    })
    mockFetchOnce(new Response(body, { status: 422, headers: { 'Content-Type': 'application/json' } }))
    const err = await api.rejectStage('a1').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(422)
    expect(err.message).toContain('field required')
    expect(err.message).toContain('too short')
  })

  it('503 response produces a friendly retry message and preserves status', async () => {
    mockFetchOnce(new Response('Service Unavailable', { status: 503 }))
    const err = await api.rejectStage('a1').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(503)
    expect(err.message).toMatch(/temporarily unavailable|try again/i)
  })

  it('network failure (fetch rejects) gives a friendly message with status 0', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))
    const err = await api.rejectStage('a1').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(0)
    expect(err.message).toMatch(/couldn'?t reach the server|network/i)
    expect(err.message).not.toContain('Failed to fetch')
  })

  it('500 with { detail: "boom" } uses the detail string directly', async () => {
    const body = JSON.stringify({ detail: 'boom' })
    mockFetchOnce(new Response(body, { status: 500, headers: { 'Content-Type': 'application/json' } }))
    const err = await api.rejectStage('a1').catch((e) => e)
    expect(err).toBeInstanceOf(ApiError)
    expect(err.status).toBe(500)
    expect(err.message).toBe('boom')
  })
})

describe('api path encoding', () => {
  it('encodes the analysis id in getAnalysis', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(
      new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
    )
    await api.getAnalysis('a/b c')
    expect(lastFetchUrl()).toContain('/analyses/a%2Fb%20c')
  })

  it('encodes the id and stage in exportStage', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue(new Response('', { status: 200 }))
    await api.exportStage('x/y', 3, 'json')
    expect(lastFetchUrl()).toContain('/analyses/x%2Fy/export/3')
  })
})
