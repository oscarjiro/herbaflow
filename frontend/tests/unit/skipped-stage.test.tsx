import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { isSkippedStage } from '@/types/api'
import { Stage1Panel } from '@/components/stages/Stage1Panel'
import { getStageStatus } from '@/components/pipeline/PipelineSidebar'
import type { AnalysisRunResponse, AnalysisStatusResponse } from '@/types/api'

function makeQueryClient() {
  return new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
}

function renderWithQuery(ui: React.ReactElement) {
  return render(
    <QueryClientProvider client={makeQueryClient()}>{ui}</QueryClientProvider>
  )
}

// ─── isSkippedStage type guard ────────────────────────────────────────────────

describe('isSkippedStage', () => {
  it('returns true for a skipped stage result', () => {
    expect(isSkippedStage({ state: 'not_applicable' })).toBe(true)
  })

  it('returns false for a normal stage result', () => {
    expect(isSkippedStage({ total_compounds: 10, plants_covered: 2, compounds: [] })).toBe(false)
  })

  it('returns false for null', () => {
    expect(isSkippedStage(null)).toBe(false)
  })

  it('returns false for undefined', () => {
    expect(isSkippedStage(undefined)).toBe(false)
  })

  it('returns false for a result with status other than skipped', () => {
    expect(isSkippedStage({ status: 'complete' })).toBe(false)
  })
})

// ─── Stage1Panel skipped rendering ───────────────────────────────────────────

describe('Stage1Panel — skipped stage', () => {
  const baseAnalysis: AnalysisRunResponse = {
    analysis_id: 'test-id',
    analysis_name: 'Test Analysis',
    status: 'stage_2_running',
    mode: 'guided',
    disease_id: null,
    current_stage: 2,
    stage_results: {
      stage_1: { state: 'not_applicable' },
    },
    parameters: null,
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
  }

  const baseStatus: AnalysisStatusResponse = {
    analysis_id: 'test-id',
    status: 'stage_2_running',
    mode: 'guided',
    current_stage: 2,
    progress: {},
    created_at: null,
    updated_at: null,
    error_message: null,
    expires_at: null,
  }

  it('renders SkippedStageNotice when stage_result is skipped', () => {
    renderWithQuery(
      <Stage1Panel
        stage={1}
        analysis={baseAnalysis}
        status={baseStatus}
        analysisId="test-id"
      />
    )
    expect(
      screen.getByText('This stage was skipped — manual input was used.')
    ).toBeInTheDocument()
  })

  it('does not render the normal compound table when stage is skipped', () => {
    renderWithQuery(
      <Stage1Panel
        stage={1}
        analysis={baseAnalysis}
        status={baseStatus}
        analysisId="test-id"
      />
    )
    expect(screen.queryByText('Total Compounds')).not.toBeInTheDocument()
  })
})

// ─── getStageStatus — skipped detection ──────────────────────────────────────

describe('getStageStatus — skipped stages', () => {
  const statusData: AnalysisStatusResponse = {
    analysis_id: 'test-id',
    status: 'stage_2_running',
    mode: 'guided',
    current_stage: 2,
    progress: {},
    created_at: null,
    updated_at: null,
    error_message: null,
    expires_at: null,
  }

  const analysisWithSkip: AnalysisRunResponse = {
    analysis_id: 'test-id',
    analysis_name: 'Test',
    status: 'stage_2_running',
    mode: 'guided',
    disease_id: null,
    current_stage: 2,
    stage_results: {
      stage_1: { state: 'not_applicable' },
    },
    parameters: null,
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
  }

  it('returns skipped for a stage whose result has status=skipped', () => {
    expect(getStageStatus(1, statusData, analysisWithSkip)).toBe('skipped')
  })

  it('returns running for the current non-skipped stage', () => {
    expect(getStageStatus(2, statusData, analysisWithSkip)).toBe('running')
  })

  it('returns future for a stage not yet reached and not skipped', () => {
    expect(getStageStatus(3, statusData, analysisWithSkip)).toBe('future')
  })
})
