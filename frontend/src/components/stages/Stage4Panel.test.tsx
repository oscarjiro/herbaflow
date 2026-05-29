/**
 * Render tests for Stage4Panel.
 *
 * Guards against Stage-4 field drift: the backend emits disease-target rows with
 * `uniprot_accession` and `score`. If the TS type / column accessors regress to
 * the old `uniprot_id` / `association_score` names, the UniProt and Open Targets
 * Score columns silently render the "—" placeholder, hiding the disease side of
 * the network-pharmacology overlap from the researcher.
 */
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { Stage4Panel } from './Stage4Panel'
import type {
  AnalysisRunResponse,
  AnalysisStatusResponse,
  Stage4Result,
} from '@/types/api'

function makeAnalysis(stage4: Stage4Result): AnalysisRunResponse {
  return {
    analysis_id: 'a1',
    analysis_name: 'test',
    status: 'stage_4_complete',
    mode: 'guided',
    disease_id: null,
    current_stage: 4,
    stage_results: { stage_4: stage4 as unknown as Record<string, unknown> },
    parameters: {},
    created_at: null,
    completed_at: null,
    expires_at: null,
    error_message: null,
  }
}

const status: AnalysisStatusResponse = {
  analysis_id: 'a1',
  status: 'stage_4_complete',
  mode: 'guided',
  current_stage: 4,
  progress: {},
  created_at: null,
  updated_at: null,
  error_message: null,
  expires_at: null,
}

function renderPanel(stage4: Stage4Result) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  return render(
    <QueryClientProvider client={queryClient}>
      <Stage4Panel
        stage={4}
        analysis={makeAnalysis(stage4)}
        status={status}
        analysisId="a1"
      />
    </QueryClientProvider>,
  )
}

describe('Stage4Panel — disease-target field mapping', () => {
  const fixture: Stage4Result = {
    disease_target_count: 1,
    targets: [
      {
        gene_symbol: 'TP53',
        uniprot_accession: 'P04637',
        score: 0.873,
        disease_name: 'Breast carcinoma',
        source: 'db_cache',
      },
    ],
  }

  it('renders the UniProt accession (not the — placeholder)', () => {
    renderPanel(fixture)
    expect(screen.getByText('P04637')).toBeInTheDocument()
  })

  it('renders the Open Targets score formatted to 3 decimals', () => {
    renderPanel(fixture)
    expect(screen.getByText('0.873')).toBeInTheDocument()
  })

  it('does not render — for a row that has both an accession and a score', () => {
    renderPanel(fixture)
    // The gene-symbol cell is present; neither value-bearing column fell back to —
    expect(screen.getByText('TP53')).toBeInTheDocument()
    expect(screen.queryByText('—')).not.toBeInTheDocument()
  })
})
