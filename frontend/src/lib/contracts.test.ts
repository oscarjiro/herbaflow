import { describe, it, expect } from 'vitest'
import analysisContract from '@shared/contracts/analysis.json'
import { analysisModeSchema } from './schemas'

describe('analysis mode contract', () => {
  it('Zod enum matches the shared contract', () => {
    expect([...analysisModeSchema.options].sort()).toEqual(
      [...analysisContract.analysis_mode].sort(),
    )
  })

  it('accepts contract modes and rejects others', () => {
    for (const m of analysisContract.analysis_mode) {
      expect(analysisModeSchema.safeParse(m).success).toBe(true)
    }
    expect(analysisModeSchema.safeParse('semi').success).toBe(false)
  })
})
