import { describe, it, expect } from 'vitest'
import { ApiError } from '@/lib/api'

describe('ApiError', () => {
  it('carries the HTTP status', () => {
    const err = new ApiError(410, 'gone')
    expect(err).toBeInstanceOf(Error)
    expect(err.status).toBe(410)
    // Status is on .status; message is the human string passed in directly.
    expect(err.message).toBe('gone')
  })

  it('has name ApiError', () => {
    const err = new ApiError(404, 'not found')
    expect(err.name).toBe('ApiError')
  })

  it('uses the passed message as-is (no "API N:" prefix)', () => {
    const err = new ApiError(500, 'internal server error')
    expect(err.message).toBe('internal server error')
  })
})
