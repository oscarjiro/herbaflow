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

describe('api.validateInChunks', () => {
  function emptyPayload() {
    return { valid: [], failed: [], normalized: [], duplicates: [], reused: 0, enriched: 0 }
  }

  function jsonResponse(body: unknown): Response {
    return new Response(JSON.stringify(body), {
      status: 200,
      headers: { 'Content-Type': 'application/json' },
    })
  }

  function lastFetchBody(callIndex: number): Record<string, unknown> {
    const calls = (globalThis.fetch as any).mock.calls
    return JSON.parse(calls[callIndex][1].body as string)
  }

  it('chunks 60 inputs into 3 sequential POSTs and merges the payloads', async () => {
    const inputs = Array.from({ length: 60 }, (_, i) => `g${i + 1}`)
    const responses = [
      jsonResponse({ ...emptyPayload(), valid: [{ id: 1 }], reused: 1, enriched: 2 }),
      jsonResponse({ ...emptyPayload(), valid: [{ id: 2 }], reused: 3, enriched: 4 }),
      jsonResponse({ ...emptyPayload(), valid: [{ id: 3 }], reused: 5, enriched: 6 }),
    ]
    let n = 0
    vi.stubGlobal('fetch', vi.fn(async () => responses[n++]))

    const result = await api.validateInChunks('target', inputs, false)

    expect((globalThis.fetch as any).mock.calls).toHaveLength(3)
    // Chunk sizes 25 / 25 / 10
    expect((lastFetchBody(0).inputs as string[]).length).toBe(25)
    expect((lastFetchBody(1).inputs as string[]).length).toBe(25)
    expect((lastFetchBody(2).inputs as string[]).length).toBe(10)
    // POSTs to the validate-inputs endpoint with the right kind
    expect(lastFetchUrl()).toContain('/analyses/validate-inputs')
    expect(lastFetchBody(0).kind).toBe('target')
    // Merged: concat valid, summed counters
    expect(result.valid).toEqual([{ id: 1 }, { id: 2 }, { id: 3 }])
    expect(result.reused).toBe(9)
    expect(result.enriched).toBe(12)
  })

  it('re-indexes a 2nd-chunk failed line (local 2) to a global line (27)', async () => {
    const inputs = Array.from({ length: 30 }, (_, i) => `g${i + 1}`)
    const responses = [
      jsonResponse(emptyPayload()),
      jsonResponse({
        ...emptyPayload(),
        failed: [{ line: 2, input: 'bad', reason: 'invalid' }],
      }),
    ]
    let n = 0
    vi.stubGlobal('fetch', vi.fn(async () => responses[n++]))

    const result = await api.validateInChunks('target', inputs, false)

    expect(result.failed).toHaveLength(1)
    // First chunk had 25 inputs → offset 25; local line 2 → global 27
    expect(result.failed[0].line).toBe(27)
    expect(result.failed[0].input).toBe('bad')
  })

  it('calls onProgress with cumulative counts ending at the total', async () => {
    const inputs = Array.from({ length: 60 }, (_, i) => `g${i + 1}`)
    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse(emptyPayload())))

    const progress: [number, number][] = []
    await api.validateInChunks('compound', inputs, false, (done, total) => {
      progress.push([done, total])
    })

    expect(progress).toEqual([
      [25, 60],
      [50, 60],
      [60, 60],
    ])
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
