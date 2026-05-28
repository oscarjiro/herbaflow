import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { Stage3Panel } from '@/components/stages/Stage3Panel'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage3Result, TargetResult } from '@/types/api'

// Mock heavy dependencies that aren't under test
vi.mock('@/components/shared/StageParamsPanel', () => ({
  StageParamsPanel: () => null,
}))
vi.mock('@/lib/stp', () => ({
  parseSTPCsv: vi.fn(() => ({ targets: [], error: null })),
  generateSTPExportCsv: vi.fn(() => ''),
}))

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

function makeTarget(overrides: Partial<TargetResult> = {}): TargetResult {
  return {
    gene_symbol: 'TP53',
    uniprot_id: 'P04637',
    compound_count: 3,
    compound_ids: ['cmp-1', 'cmp-2', 'cmp-3'],
    source: 'chembl',
    ...overrides,
  }
}

function makeStage3Result(overrides: Partial<Stage3Result> = {}): Stage3Result {
  return {
    target_count: 2,
    coverage_pct: 85.5,
    targets: [
      makeTarget({ gene_symbol: 'TP53', uniprot_id: 'P04637', compound_count: 3 }),
      makeTarget({ gene_symbol: 'EGFR', uniprot_id: 'P00533', compound_count: 2, source: 'pubchem_bioassay' }),
    ],
    compound_sources: {},
    uncovered_compounds: [],
    ...overrides,
  }
}

function makeAnalysis(stage3Result: Stage3Result | null, stage2Compounds: unknown[] = []): AnalysisRunResponse {
  return {
    analysis_id: 'test-id',
    analysis_name: 'Test Analysis',
    status: 'complete',
    mode: 'guided',
    disease_id: null,
    current_stage: null,
    stage_results: {
      ...(stage3Result ? { stage_3: stage3Result } : {}),
      ...(stage2Compounds.length > 0 ? { stage_2: { passed: 2, failed: 0, np_exceptions: 0, compounds: stage2Compounds } } : {}),
    },
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

function renderStage3(result: Stage3Result | null = makeStage3Result()) {
  return render(
    React.createElement(Stage3Panel, {
      stage: 3,
      analysis: makeAnalysis(result),
      status: mockStatus,
      analysisId: 'test-id',
    }),
    { wrapper: makeWrapper() }
  )
}

describe('Stage3Panel', () => {
  it('renders empty state when no result', () => {
    renderStage3(null)
    expect(screen.getByText('Stage 3 results not yet available')).toBeInTheDocument()
  })

  it('renders target coverage percentage from coverage_pct field (regression: not coverage_percent)', () => {
    renderStage3(makeStage3Result({ coverage_pct: 85.5 }))
    // StatCard should show "85.5%"
    expect(screen.getByText('85.5%')).toBeInTheDocument()
  })

  it('renders Coverage stat card label', () => {
    renderStage3()
    expect(screen.getByText('Coverage')).toBeInTheDocument()
  })

  it('renders Targets Found stat card with correct count', () => {
    renderStage3(makeStage3Result({ target_count: 42, targets: [makeTarget()] }))
    expect(screen.getByText('Targets Found')).toBeInTheDocument()
    expect(screen.getByText('42')).toBeInTheDocument()
  })

  it('renders target table with gene_symbol column header', () => {
    renderStage3()
    expect(screen.getByText('Gene Symbol')).toBeInTheDocument()
  })

  it('renders gene symbols in the target table', () => {
    renderStage3()
    // Genes appear in the gene badge list AND the table — use getAllByText
    expect(screen.getAllByText('TP53').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('EGFR').length).toBeGreaterThanOrEqual(1)
  })

  it('renders Binding Compounds column', () => {
    renderStage3()
    expect(screen.getByText('Binding Compounds')).toBeInTheDocument()
  })

  it('renders UniProt Accession column', () => {
    renderStage3()
    expect(screen.getByText('UniProt Accession')).toBeInTheDocument()
  })

  it('renders Source column', () => {
    renderStage3()
    expect(screen.getByText('Source')).toBeInTheDocument()
  })

  it('renders uncovered compounds section when uncovered_compounds is non-empty', () => {
    const result = makeStage3Result({
      coverage_pct: 60.0,
      uncovered_compounds: [
        { compound_id: 'uc-1', canonical_name: 'Uncovered Compound A', smiles: 'CC' },
      ],
    })
    renderStage3(result)
    expect(screen.getByText('Coverage Details')).toBeInTheDocument()
    expect(screen.getAllByText(/1 uncovered/).length).toBeGreaterThanOrEqual(1)
  })

  it('shows all compounds covered message when uncovered_compounds is empty', () => {
    renderStage3(makeStage3Result({ uncovered_compounds: [] }))
    expect(screen.getByText('All compounds covered ✓')).toBeInTheDocument()
  })

  it('renders without crash when compounds list is empty', () => {
    const result = makeStage3Result({ target_count: 0, targets: [], coverage_pct: 0 })
    renderStage3(result)
    expect(screen.getByText('No results')).toBeInTheDocument()
  })

  it('coverage_pct 0% renders correctly without crash', () => {
    renderStage3(makeStage3Result({ coverage_pct: 0 }))
    expect(screen.getByText('0.0%')).toBeInTheDocument()
  })

  it('coverage_pct 100% renders correctly', () => {
    renderStage3(makeStage3Result({ coverage_pct: 100 }))
    expect(screen.getByText('100.0%')).toBeInTheDocument()
  })
})
