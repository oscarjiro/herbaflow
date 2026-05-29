import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { Stage1Panel } from '@/components/stages/Stage1Panel'
import { analysisFixture } from '@/mocks/data'
import type { AnalysisRunResponse, AnalysisStatusResponse } from '@/types/api'

// Regression: the analysis fixture's `stage_results` must be keyed `stage_1`..`stage_8`,
// matching the `stage_${stage}` lookup every stage panel performs. If the keys drift
// back to '1'..'8', panels read `undefined` and silently render their empty state,
// so fixture-backed panel tests would assert against nothing.

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

const mockStatus: AnalysisStatusResponse = {
  analysis_id: 'test-id-1',
  status: 'complete',
  mode: 'guided',
  current_stage: null,
  progress: {},
  created_at: null,
  updated_at: null,
  error_message: null,
  expires_at: null,
}

describe('analysis fixture stage_results keys', () => {
  it('is keyed stage_1..stage_8 (the keys panels read)', () => {
    const keys = Object.keys(analysisFixture.stage_results)
    expect(keys).toEqual([
      'stage_1', 'stage_2', 'stage_3', 'stage_4',
      'stage_5', 'stage_6', 'stage_7', 'stage_8',
    ])
  })

  it('Stage1Panel renders data from the re-keyed fixture (not its empty state)', () => {
    render(
      React.createElement(Stage1Panel, {
        stage: 1,
        analysis: analysisFixture as unknown as AnalysisRunResponse,
        status: mockStatus,
        analysisId: 'test-id-1',
      }),
      { wrapper: makeWrapper() }
    )

    // total_compounds: 42 from stage_results.stage_1 — only rendered when the
    // fixture key resolves; the empty state ("Stage 1 results not yet available")
    // must NOT appear.
    expect(screen.getByText('Total Compounds')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
    expect(screen.queryByText(/results not yet available/i)).not.toBeInTheDocument()
  })
})
