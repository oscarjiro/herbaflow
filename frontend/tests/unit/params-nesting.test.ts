// frontend/tests/unit/params-nesting.test.ts
import { describe, it, expect } from 'vitest'
import { DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'
import { nestAdvancedParams, nestedParamsSchema } from '@/lib/schemas'

describe('nestAdvancedParams', () => {
  it('groups flat fields under their stage keys', () => {
    const nested = nestAdvancedParams(DEFAULT_PARAMS)
    expect(nested.adme.max_mw).toBe(DEFAULT_PARAMS.max_mw)
    expect(nested.target.min_pchembl).toBe(DEFAULT_PARAMS.min_pchembl)
    expect(nested.ppi.min_confidence).toBe(DEFAULT_PARAMS.min_confidence)
    expect(nested.enrichment.sources).toEqual(DEFAULT_PARAMS.sources)
    // no flat leakage
    expect((nested as Record<string, unknown>).max_mw).toBeUndefined()
  })

  it('validates the nested shape', () => {
    const nested = nestAdvancedParams(DEFAULT_PARAMS)
    expect(nestedParamsSchema.safeParse(nested).success).toBe(true)
  })

  it('rejects a bad nested value', () => {
    const bad = nestAdvancedParams({ ...DEFAULT_PARAMS, min_pchembl: 99 })
    expect(nestedParamsSchema.safeParse(bad).success).toBe(false)
  })
})
