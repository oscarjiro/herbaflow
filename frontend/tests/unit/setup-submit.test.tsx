import { describe, it, expect } from 'vitest'
import { buildCreateRequest } from '@/pages/SetupPage'
import { DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'

describe('buildCreateRequest', () => {
  it('standard mode: nested params, no control keys, no manual inputs', () => {
    const req = buildCreateRequest({
      name: 'n', mode: 'guided', plantIds: ['p1'], diseaseId: 'd1',
      params: DEFAULT_PARAMS, inputMode: 'standard',
      diseaseInputMode: 'disease',
      parsedCompounds: [], parsedTargets: [], parsedDiseaseTargets: [],
    })
    expect(req.parameters.adme.max_mw).toBe(DEFAULT_PARAMS.max_mw)
    expect((req.parameters as Record<string, unknown>)._input_mode).toBeUndefined()
    expect(req.compounds).toBeUndefined()
    expect(req.plant_ids).toEqual(['p1'])
  })

  it('manual compounds: compounds inline, plant_ids empty', () => {
    const req = buildCreateRequest({
      name: 'n', mode: 'guided', plantIds: [], diseaseId: 'd1',
      params: DEFAULT_PARAMS, inputMode: 'manual_compounds',
      diseaseInputMode: 'disease',
      parsedCompounds: ['CCO'], parsedTargets: [], parsedDiseaseTargets: [],
    })
    expect(req.compounds).toEqual(['CCO'])
    expect(req.plant_ids).toEqual([])
  })

  it('manual disease targets: lifted to top-level, disease_id null', () => {
    const req = buildCreateRequest({
      name: 'n', mode: 'guided', plantIds: ['p1'], diseaseId: null,
      params: DEFAULT_PARAMS, inputMode: 'standard',
      diseaseInputMode: 'manual_targets',
      parsedCompounds: [], parsedTargets: [], parsedDiseaseTargets: ['TP53'],
    })
    expect(req.manual_disease_targets).toEqual(['TP53'])
    expect(req.disease_id).toBeNull()
  })
})
