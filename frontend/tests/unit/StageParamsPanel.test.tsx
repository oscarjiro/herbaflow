import { render, screen, fireEvent } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StageParamsPanel } from '@/components/shared/StageParamsPanel'

// Mock useResetFromStage to avoid real API calls
vi.mock('@/hooks/useResetFromStage', () => ({
  useResetFromStage: () => ({
    mutate: vi.fn(),
    isPending: false,
  }),
}))

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

// Stage 2 uses 'adme' params; open the panel to reveal the rerun button
describe('StageParamsPanel — isDirty detection', () => {
  const baseParams = {
    adme: {
      max_mw: 500,
      max_logp: 5.0,
      max_hbd: 5,
      max_hba: 10,
      max_tpsa: 140.0,
      max_rotatable_bonds: 10,
      apply_veber: true,
      apply_pains: false,
      np_exception_threshold: 0.5,
    },
  }

  function renderStage2(canRerun = true, currentParams = baseParams) {
    renderWithQuery(
      <StageParamsPanel
        stage={2}
        analysisId="test-id"
        currentParams={currentParams}
        canRerun={canRerun}
      />
    )
    // Open the collapsible panel
    fireEvent.click(screen.getByText('Stage Parameters'))
  }

  it('rerun button is disabled when params are unchanged from initial values', () => {
    renderStage2()
    const rerunBtn = screen.getByRole('button', {
      name: /rerun stage 2 with updated parameters/i,
    })
    expect(rerunBtn).toBeDisabled()
  })

  it('rerun button becomes enabled after changing a numeric param', () => {
    renderStage2()
    // Find the Max MW input and change it
    const maxMwInput = screen.getByDisplayValue('500')
    fireEvent.change(maxMwInput, { target: { value: '400' } })
    const rerunBtn = screen.getByRole('button', {
      name: /rerun stage 2 with updated parameters/i,
    })
    expect(rerunBtn).not.toBeDisabled()
  })

  it('rerun button becomes enabled after toggling a boolean param', () => {
    renderStage2()
    // apply_veber is true by default — toggle it off
    const veber = screen.getByRole('checkbox', { name: /apply veber rules/i })
    fireEvent.click(veber)
    const rerunBtn = screen.getByRole('button', {
      name: /rerun stage 2 with updated parameters/i,
    })
    expect(rerunBtn).not.toBeDisabled()
  })

  it('rerun button reverts to disabled after restoring original value', () => {
    renderStage2()
    const maxMwInput = screen.getByDisplayValue('500')
    fireEvent.change(maxMwInput, { target: { value: '400' } })
    // Restore
    fireEvent.change(maxMwInput, { target: { value: '500' } })
    const rerunBtn = screen.getByRole('button', {
      name: /rerun stage 2 with updated parameters/i,
    })
    expect(rerunBtn).toBeDisabled()
  })

  it('rerun button is not rendered when canRerun is false', () => {
    renderStage2(false)
    expect(
      screen.queryByRole('button', { name: /rerun stage 2 with updated parameters/i })
    ).not.toBeInTheDocument()
  })
})

// Stage 8 uses 'enrichment' params with a sources array — test array-type isDirty
describe('StageParamsPanel — array param isDirty (Stage 8)', () => {
  const enrichmentParams = {
    enrichment: {
      fdr_threshold: 0.05,
      min_gene_set_size: 10,
      max_gene_set_size: 500,
      sources: ['GO:BP', 'GO:MF'],
    },
  }

  function renderStage8(currentParams = enrichmentParams) {
    renderWithQuery(
      <StageParamsPanel
        stage={8}
        analysisId="test-id"
        currentParams={currentParams}
        canRerun={true}
      />
    )
    fireEvent.click(screen.getByText('Stage Parameters'))
  }

  it('rerun button is disabled when sources array has same elements in different order', () => {
    // Render with ['GO:BP', 'GO:MF'] — then simulate toggling GO:BP off then on
    // to produce same logical set; button should remain disabled
    renderStage8()
    const rerunBtn = screen.getByRole('button', {
      name: /rerun stage 8 with updated parameters/i,
    })
    // Toggle GO:BP off
    fireEvent.click(screen.getByText('GO:BP'))
    // Toggle GO:BP back on — logical sources set is identical to initial
    fireEvent.click(screen.getByText('GO:BP'))
    expect(rerunBtn).toBeDisabled()
  })

  it('rerun button becomes enabled after removing a source from the array', () => {
    renderStage8()
    const rerunBtn = screen.getByRole('button', {
      name: /rerun stage 8 with updated parameters/i,
    })
    // Remove GO:MF — sources array shrinks, isDirty should be true
    fireEvent.click(screen.getByText('GO:MF'))
    expect(rerunBtn).not.toBeDisabled()
  })
})
