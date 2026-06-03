import { describe, it, expect } from 'vitest'
import { getStageStatus } from './PipelineSidebar'
import type { AnalysisStatusResponse, AnalysisRunResponse } from '@/types/api'

const status = { status: 'stage_4_running', current_stage: 4 } as AnalysisStatusResponse

function analysisWith(stageResults: Record<string, unknown>) {
  return { stage_results: stageResults } as unknown as AnalysisRunResponse
}

describe('getStageStatus from state', () => {
  it('treats not_applicable as skipped (non-clickable)', () => {
    const a = analysisWith({ stage_1: { state: 'not_applicable' } })
    expect(getStageStatus(1, status, a)).toBe('skipped')
  })

  it('treats user_provided as completed (clickable) even when stage > current_stage', () => {
    // stage 6 is after the current stage (4), so without the state branch
    // the existing logic would return 'future' — the state branch must fire first
    const a = analysisWith({ stage_6: { state: 'user_provided' } })
    expect(getStageStatus(6, status, a)).toBe('completed')
  })
})
