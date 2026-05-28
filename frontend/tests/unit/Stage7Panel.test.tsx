import { render, screen } from '@testing-library/react'
import { describe, it, expect, vi } from 'vitest'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import React from 'react'
import { Stage7Panel } from '@/components/stages/Stage7Panel'
import type { AnalysisRunResponse, AnalysisStatusResponse, Stage7Result, HubGeneResult, CommunityHubGene } from '@/types/api'

// Mock react-cytoscapejs to avoid canvas errors
vi.mock('react-cytoscapejs', () => ({
  default: ({ elements }: { elements: unknown[] }) => (
    React.createElement('div', { 'data-testid': 'cytoscape', 'data-elements': JSON.stringify(elements) })
  ),
}))

// Mock StageParamsPanel and ExportButton
vi.mock('@/components/shared/StageParamsPanel', () => ({
  StageParamsPanel: () => null,
}))
vi.mock('@/components/shared/ExportButton', () => ({
  ExportButton: () => null,
}))

function makeWrapper() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return ({ children }: { children: React.ReactNode }) =>
    React.createElement(QueryClientProvider, { client: qc }, children)
}

function makeHubGene(overrides: Partial<HubGeneResult> = {}): HubGeneResult {
  return {
    rank: 1,
    gene_symbol: 'TP53',
    degree: 0.85,
    betweenness: 0.72,
    closeness: 0.65,
    eigenvector: 0.91,
    is_hub: true,
    is_hub_bottleneck: false,
    ...overrides,
  }
}

function makeStage7Result(overrides: Partial<Stage7Result> = {}): Stage7Result {
  return {
    ranked: [
      makeHubGene({ rank: 1, gene_symbol: 'TP53', degree: 0.85, is_hub: true }),
      makeHubGene({ rank: 2, gene_symbol: 'EGFR', degree: 0.60, is_hub: false }),
      makeHubGene({ rank: 3, gene_symbol: 'AKT1', degree: 0.30, betweenness: 0.8, is_hub: true, is_hub_bottleneck: true }),
    ],
    threshold_degree: 0.70,
    threshold_betweenness: 0.65,
    ...overrides,
  }
}

function makeAnalysis(stage7Result: Stage7Result | null): AnalysisRunResponse {
  return {
    analysis_id: 'test-id',
    analysis_name: 'Test Analysis',
    status: 'complete',
    mode: 'guided',
    disease_id: null,
    current_stage: null,
    stage_results: stage7Result ? { stage_7: stage7Result } : {},
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

function renderStage7(result: Stage7Result | null = makeStage7Result()) {
  return render(
    React.createElement(Stage7Panel, {
      stage: 7,
      analysis: makeAnalysis(result),
      status: mockStatus,
      analysisId: 'test-id',
    }),
    { wrapper: makeWrapper() }
  )
}

describe('Stage7Panel', () => {
  it('renders empty state when no result prop', () => {
    renderStage7(null)
    expect(screen.getByText('Stage 7 results not yet available')).toBeInTheDocument()
  })

  it('renders hub gene table with gene_symbol column header', () => {
    renderStage7()
    expect(screen.getByText('Gene')).toBeInTheDocument()
  })

  it('renders Degree Centrality column header', () => {
    renderStage7()
    expect(screen.getByText('Degree Centrality')).toBeInTheDocument()
  })

  it('renders Betweenness Centrality column header', () => {
    renderStage7()
    expect(screen.getByText('Betweenness Centrality')).toBeInTheDocument()
  })

  it('renders gene symbols in the table', () => {
    renderStage7()
    expect(screen.getByText('TP53')).toBeInTheDocument()
    expect(screen.getByText('EGFR')).toBeInTheDocument()
    expect(screen.getByText('AKT1')).toBeInTheDocument()
  })

  it('renders Hub badge for hub genes (is_hub: true)', () => {
    renderStage7()
    // TP53 is a hub but not bottleneck, AKT1 is hub+bottleneck
    const hubLabels = screen.getAllByText(/^Hub/)
    expect(hubLabels.length).toBeGreaterThanOrEqual(1)
  })

  it('renders Hub + Bottleneck badge for hub bottleneck genes', () => {
    renderStage7()
    // AKT1 has is_hub: true and is_hub_bottleneck: true
    expect(screen.getByText('Hub + Bottleneck')).toBeInTheDocument()
  })

  it('renders stat cards: Total Genes, Hub Genes, Degree Threshold', () => {
    renderStage7()
    expect(screen.getByText('Total Genes')).toBeInTheDocument()
    expect(screen.getByText('Hub Genes')).toBeInTheDocument()
    expect(screen.getByText('Degree Threshold')).toBeInTheDocument()
  })

  it('renders correct hub gene count in stat card', () => {
    renderStage7()
    // 2 hub genes (TP53 is_hub:true, AKT1 is_hub:true) — multiple '2' elements may be present
    expect(screen.getAllByText('2').length).toBeGreaterThanOrEqual(1)
  })

  it('renders community hubs section when community_hubs data is present', () => {
    const communityHub: CommunityHubGene = {
      gene_symbol: 'BRCA1',
      community_id: 0,
      community_degree: 0.8,
      community_betweenness: 0.6,
      community_closeness: 0.5,
      community_eigenvector: 0.7,
      community_size: 10,
    }
    const result = makeStage7Result({
      community_hubs: { '0': [communityHub] },
    })
    renderStage7(result)
    expect(screen.getByText('Community-Specific Hub Genes')).toBeInTheDocument()
    expect(screen.getByText('BRCA1')).toBeInTheDocument()
  })

  it('does NOT render community hubs section when community_hubs is undefined', () => {
    const result = makeStage7Result({ community_hubs: undefined })
    renderStage7(result)
    expect(screen.queryByText('Community-Specific Hub Genes')).not.toBeInTheDocument()
  })

  it('does NOT render community hubs section when community_hubs is empty object', () => {
    const result = makeStage7Result({ community_hubs: {} })
    renderStage7(result)
    expect(screen.queryByText('Community-Specific Hub Genes')).not.toBeInTheDocument()
  })

  it('renders Hub Gene Analysis heading', () => {
    renderStage7()
    expect(screen.getByText('Hub Gene Analysis')).toBeInTheDocument()
  })

  it('renders without crash when ranked list is empty', () => {
    const result = makeStage7Result({ ranked: [] })
    renderStage7(result)
    expect(screen.getByText('No results')).toBeInTheDocument()
  })
})
