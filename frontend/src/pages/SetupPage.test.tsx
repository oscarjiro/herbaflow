import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import { DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'
import { validateSetupForm } from '@/lib/schemas'

import SetupPage, {
  buildSetupFormData,
  buildCreateRequest,
  type BuildSetupFormDataArgs,
} from './SetupPage'

// jsdom shims for the Radix/cmdk comboboxes rendered inside SetupPage's selectors.
Element.prototype.hasPointerCapture = vi.fn() as unknown as typeof Element.prototype.hasPointerCapture
Element.prototype.scrollIntoView = vi.fn()
globalThis.ResizeObserver = class ResizeObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
}

// Mock the data/navigation hooks so SetupPage renders without a router or query client.
vi.mock('react-router-dom', () => ({ useNavigate: () => vi.fn() }))
vi.mock('@/hooks/useStartAnalysis', () => ({
  useStartAnalysis: () => ({ mutate: vi.fn(), isPending: false, isError: false, error: null }),
}))
vi.mock('@/hooks/usePlants', () => ({ usePlants: () => ({ data: [], isLoading: false }) }))
vi.mock('@/hooks/useDiseases', () => ({ useDiseases: () => ({ data: [], isLoading: false }) }))

/**
 * Regression: the setup form must validate the SAME nested parameter shape it sends
 * to the server. Validating the flat accordion state against nestedParamsSchema fails
 * every submit with "Invalid input: expected object, received undefined", so no
 * analysis could ever start. These tests would have caught that.
 */

const base: BuildSetupFormDataArgs = {
  name: 'Analysis — 2026-01-01',
  mode: 'guided',
  inputMode: 'standard',
  diseaseInputMode: 'disease',
  plantIds: ['plant-1'],
  diseaseId: 'disease-1',
  params: DEFAULT_PARAMS,
  parsedCompounds: [],
  parsedTargets: [],
  parsedDiseaseTargets: [],
}

describe('buildSetupFormData → validateSetupForm', () => {
  it('nests advanced params into the PipelineConfig group shape', () => {
    const data = buildSetupFormData(base)
    const params = data.parameters as Record<string, unknown>
    expect(params).toHaveProperty('adme')
    expect(params.adme).toMatchObject({ max_mw: DEFAULT_PARAMS.max_mw })
    expect(params).toHaveProperty('enrichment')
  })

  it('standard + disease with defaults validates', () => {
    const data = buildSetupFormData(base)
    const { success, errors } = validateSetupForm('standard', 'disease', data)
    expect(errors).toEqual({})
    expect(success).toBe(true)
  })

  it('manual_compounds + disease with defaults validates', () => {
    const data = buildSetupFormData({
      ...base,
      inputMode: 'manual_compounds',
      parsedCompounds: ['CCO'],
    })
    const { success } = validateSetupForm('manual_compounds', 'disease', data)
    expect(success).toBe(true)
  })

  it('manual_targets + disease with defaults validates', () => {
    const data = buildSetupFormData({
      ...base,
      inputMode: 'manual_targets',
      parsedTargets: ['TP53'],
    })
    const { success } = validateSetupForm('manual_targets', 'disease', data)
    expect(success).toBe(true)
  })

  it('manual disease-targets mode validates', () => {
    const data = buildSetupFormData({
      ...base,
      diseaseInputMode: 'manual_targets',
      parsedDiseaseTargets: ['TP53'],
    })
    const { success } = validateSetupForm('standard', 'manual_targets', data)
    expect(success).toBe(true)
  })

  it('disease mode with no disease selected reports the friendly "Select a disease" message', () => {
    // Regression: a null disease_id used to trip Zod's raw type error
    // ("expected string, received null") instead of the humanized message.
    const data = buildSetupFormData({ ...base, diseaseId: null })
    const { success, errors } = validateSetupForm('standard', 'disease', data)
    expect(success).toBe(false)
    expect(errors.disease_id).toBe('Select a disease')
  })
})

describe('buildCreateRequest — disease-target lenient parity', () => {
  const reqBase = {
    name: 'x',
    mode: 'guided' as const,
    plantIds: [],
    diseaseId: null,
    params: DEFAULT_PARAMS,
    inputMode: 'standard' as const,
    diseaseInputMode: 'manual_targets' as const,
    parsedCompounds: [],
    parsedTargets: [],
    parsedDiseaseTargets: ['XYZ'],
  }

  it('sends skip_disease_validation when disease targets are lenient', () => {
    const req = buildCreateRequest({ ...reqBase, lenientDiseaseTargets: true })
    expect(req.skip_disease_validation).toBe(true)
    expect(req.manual_disease_targets).toEqual(['XYZ'])
  })

  it('omits skip_disease_validation when not lenient', () => {
    const req = buildCreateRequest({ ...reqBase, lenientDiseaseTargets: false })
    expect(req.skip_disease_validation).toBeUndefined()
  })
})

describe('SetupPage — Plants and Disease input modes are independent', () => {
  it('changing the Plants input mode does not reset the Disease input mode', async () => {
    // Regression: switching the Plants segmented toggle used to force the Disease
    // toggle back to "Select Disease". They must stay independent.
    const user = userEvent.setup()
    render(<SetupPage />)

    // Switch Disease to manual targets → its textarea appears.
    await user.click(screen.getByTestId('disease-input-mode-manual'))
    expect(screen.getByLabelText('Disease targets')).toBeInTheDocument()

    // Switch Plants to manual compounds.
    await user.click(screen.getByTestId('input-mode-manual'))
    expect(screen.getByLabelText('Compounds')).toBeInTheDocument()

    // Disease must STILL be in manual-targets mode.
    expect(screen.getByLabelText('Disease targets')).toBeInTheDocument()
  })
})
