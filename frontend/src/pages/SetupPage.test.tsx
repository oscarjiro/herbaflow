import { describe, it, expect } from 'vitest'

import { DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'
import { validateSetupForm } from '@/lib/schemas'

import { buildSetupFormData, type BuildSetupFormDataArgs } from './SetupPage'

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
})
