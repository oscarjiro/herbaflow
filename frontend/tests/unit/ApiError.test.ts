import { describe, it, expect } from 'vitest'
import { ApiError } from '@/lib/api'

describe('ApiError', () => {
  it('carries the HTTP status', () => {
    const err = new ApiError(410, 'gone')
    expect(err).toBeInstanceOf(Error)
    expect(err.status).toBe(410)
    expect(err.message).toContain('410')
  })

  it('has name ApiError', () => {
    const err = new ApiError(404, 'not found')
    expect(err.name).toBe('ApiError')
  })

  it('formats message as "API <status>: <body>"', () => {
    const err = new ApiError(500, 'internal server error')
    expect(err.message).toBe('API 500: internal server error')
  })
})
