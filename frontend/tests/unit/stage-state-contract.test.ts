import { describe, it, expect } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { STAGE_STATES, getStageState, getStageInputs } from '@/types/api'

describe('stage state contract', () => {
  it('matches the shared contract enum', () => {
    const contract = JSON.parse(
      readFileSync(resolve(__dirname, '../../../shared/contracts/analysis.json'), 'utf-8'),
    )
    expect([...STAGE_STATES].sort()).toEqual([...contract.stage_state].sort())
  })

  it('defaults unknown results to computed', () => {
    expect(getStageState(undefined)).toBe('computed')
    expect(getStageState({ foo: 1 })).toBe('computed')
    expect(getStageState({ state: 'user_provided' })).toBe('user_provided')
    expect(getStageState({ state: 'not_applicable' })).toBe('not_applicable')
  })

  it('reads the inputs block when present', () => {
    expect(getStageInputs({ state: 'computed' })).toBeNull()
    expect(
      getStageInputs({ inputs: { rejected: ['X'], normalized: [{ from: 'A', to: 'A1' }], unrecognized: [] } }),
    ).toEqual({ rejected: ['X'], normalized: [{ from: 'A', to: 'A1' }], unrecognized: [] })
  })
})
