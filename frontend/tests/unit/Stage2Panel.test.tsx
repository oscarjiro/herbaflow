import { render, screen, fireEvent } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { Stage2Panel } from '@/components/stages/Stage2Panel'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage2Result, AdmeCompoundResult } from '@/types/api'

// Mock StageParamsPanel to keep tests focused
vi.mock('@/components/shared/StageParamsPanel', () => ({
  StageParamsPanel: () => null,
}))

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

function makeCompound(overrides: Partial<AdmeCompoundResult> = {}): AdmeCompoundResult {
  return {
    compound_id: 'cmp-1',
    canonical_name: 'Test Compound',
    plant_ids: [],
    adme_pass: true,
    is_np_exception: false,
    molecular_weight: 350.5,
    logp: 2.5,
    tpsa: 80.1,
    hbond_donors: 1,
    hbond_acceptors: 4,
    np_likeness_score: 0.5,
    rotatable_bonds: 3,
    is_pains_positive: false,
    ...overrides,
  }
}

function makeStage2Result(overrides: Partial<Stage2Result> = {}): Stage2Result {
  return {
    passed: 2,
    failed: 1,
    np_exceptions: 0,
    compounds: [
      makeCompound({ compound_id: 'cmp-1', canonical_name: 'Quercetin', adme_pass: true }),
      makeCompound({ compound_id: 'cmp-2', canonical_name: 'Kaempferol', adme_pass: true }),
      makeCompound({ compound_id: 'cmp-3', canonical_name: 'BigMol', adme_pass: false }),
    ],
    ...overrides,
  }
}

function makeAnalysis(stage2Result: Stage2Result | null): AnalysisRunResponse {
  return {
    analysis_id: 'test-id',
    analysis_name: 'Test Analysis',
    status: 'complete',
    mode: 'guided',
    disease_id: null,
    current_stage: null,
    stage_results: stage2Result ? { stage_2: stage2Result } : {},
    parameters: {},
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
  }
}

const mockStatus: AnalysisStatusResponse = {
  analysis_id: 'test-id',
  status: 'complete',
  mode: 'guided',
  current_stage: null,
  progress: {},
  created_at: null,
  updated_at: null,
  error_message: null,
  expires_at: null,
}

function renderStage2(result: Stage2Result | null = makeStage2Result()) {
  return render(
    React.createElement(Stage2Panel, {
      stage: 2,
      analysis: makeAnalysis(result),
      status: mockStatus,
      analysisId: 'test-id',
    }),
    { wrapper: makeWrapper() }
  )
}

describe('Stage2Panel', () => {
  it('renders empty state when no result', () => {
    renderStage2(null)
    expect(screen.getByText('Stage 2 results not yet available')).toBeInTheDocument()
  })

  it('renders ADME numeric columns: MW, LogP, TPSA headers are present', () => {
    renderStage2()
    expect(screen.getByText('MW (Da)')).toBeInTheDocument()
    expect(screen.getByText('LogP')).toBeInTheDocument()
    expect(screen.getByText('TPSA (Å²)')).toBeInTheDocument()
  })

  it('renders HBD and HBA column headers', () => {
    renderStage2()
    expect(screen.getByText('HBD')).toBeInTheDocument()
    expect(screen.getByText('HBA')).toBeInTheDocument()
  })

  it('renders compound names in the table', () => {
    renderStage2()
    expect(screen.getByText('Quercetin')).toBeInTheDocument()
    expect(screen.getByText('Kaempferol')).toBeInTheDocument()
    expect(screen.getByText('BigMol')).toBeInTheDocument()
  })

  it('shows Pass (NP) badge for compound with is_np_exception: true (NP badge regression)', () => {
    const result = makeStage2Result({
      np_exceptions: 1,
      compounds: [
        makeCompound({
          compound_id: 'np-1',
          canonical_name: 'NP Compound',
          adme_pass: false,
          is_np_exception: true,
        }),
      ],
    })
    renderStage2(result)
    expect(screen.getByText('Pass (NP)')).toBeInTheDocument()
  })

  it('shows Pass badge for compounds that pass ADME (not NP exception)', () => {
    renderStage2()
    // Quercetin and Kaempferol both have adme_pass: true
    const passBadges = screen.getAllByText('Pass')
    expect(passBadges.length).toBeGreaterThanOrEqual(2)
  })

  it('shows Fail badge for compounds that fail ADME', () => {
    renderStage2()
    expect(screen.getByText('Fail')).toBeInTheDocument()
  })

  it('renders passed/failed counts in stat cards', () => {
    renderStage2()
    // Result has passed: 2, failed: 1 — check text appears in the document
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('1').length).toBeGreaterThanOrEqual(1)
  })

  it('renders All/Passed/Failed filter tabs', () => {
    renderStage2()
    expect(screen.getByRole('button', { name: 'All' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Passed' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Failed' })).toBeInTheDocument()
  })

  it('filter tab: Passed shows only passing compounds', () => {
    renderStage2()
    fireEvent.click(screen.getByRole('button', { name: 'Passed' }))
    expect(screen.getByText('Quercetin')).toBeInTheDocument()
    expect(screen.getByText('Kaempferol')).toBeInTheDocument()
    expect(screen.queryByText('BigMol')).not.toBeInTheDocument()
  })

  it('filter tab: Failed shows only failing compounds', () => {
    renderStage2()
    fireEvent.click(screen.getByRole('button', { name: 'Failed' }))
    expect(screen.queryByText('Quercetin')).not.toBeInTheDocument()
    expect(screen.queryByText('Kaempferol')).not.toBeInTheDocument()
    expect(screen.getByText('BigMol')).toBeInTheDocument()
  })

  it('filter tab: All shows all compounds after switching back', () => {
    renderStage2()
    fireEvent.click(screen.getByRole('button', { name: 'Passed' }))
    fireEvent.click(screen.getByRole('button', { name: 'All' }))
    expect(screen.getByText('Quercetin')).toBeInTheDocument()
    expect(screen.getByText('Kaempferol')).toBeInTheDocument()
    expect(screen.getByText('BigMol')).toBeInTheDocument()
  })

  it('NP exception compounds are included in Passed filter tab', () => {
    const result = makeStage2Result({
      np_exceptions: 1,
      passed: 2,
      failed: 0,
      compounds: [
        makeCompound({ compound_id: 'np-1', canonical_name: 'NP Compound', adme_pass: false, is_np_exception: true }),
        makeCompound({ compound_id: 'pass-1', canonical_name: 'Pass Compound', adme_pass: true, is_np_exception: false }),
      ],
    })
    renderStage2(result)
    fireEvent.click(screen.getByRole('button', { name: 'Passed' }))
    expect(screen.getByText('NP Compound')).toBeInTheDocument()
    expect(screen.getByText('Pass Compound')).toBeInTheDocument()
  })

  it('renders empty state without crash when compounds list is empty', () => {
    const result = makeStage2Result({ passed: 0, failed: 0, np_exceptions: 0, compounds: [] })
    renderStage2(result)
    // Table renders with no rows — should show No results
    expect(screen.getByText('No results')).toBeInTheDocument()
  })
})
