// frontend/tests/unit/params-contract-agreement.test.ts
import { describe, it, expect } from 'vitest'
import contract from '@shared/contracts/analysis.json'
import {
  admeGroupSchema, targetGroupSchema, diseaseTargetsGroupSchema,
  ppiGroupSchema, hubGenesGroupSchema, enrichmentGroupSchema,
} from '@/lib/schemas'

const groups = {
  adme: admeGroupSchema, target: targetGroupSchema,
  disease_targets: diseaseTargetsGroupSchema, ppi: ppiGroupSchema,
  hub_genes: hubGenesGroupSchema, enrichment: enrichmentGroupSchema,
} as const

// Contract fields the setup form intentionally does NOT surface. Every backend
// field is optional, so an un-exposed field is not a contract gap — it just
// isn't overridden at create time. Update this when the UI exposes a control.
const UI_OMITTED: Record<string, string[]> = {}

const contractParams = contract.pipeline_parameters as Record<string, Record<string, unknown>>

describe('zod param groups vs the shared contract', () => {
  it('group names match exactly', () => {
    expect(Object.keys(groups).sort()).toEqual(Object.keys(contractParams).sort())
  })

  it('every zod field exists in the contract (no unknown key -> never trips backend extra=forbid)', () => {
    for (const [name, schema] of Object.entries(groups)) {
      const zodKeys = Object.keys((schema as { shape: Record<string, unknown> }).shape)
      const contractKeys = Object.keys(contractParams[name])
      for (const k of zodKeys) expect(contractKeys, `${name}.${k}`).toContain(k)
    }
  })

  it('the only contract fields the form omits are the documented UI-omitted ones', () => {
    for (const [name, schema] of Object.entries(groups)) {
      const zodKeys = new Set(Object.keys((schema as { shape: Record<string, unknown> }).shape))
      const contractKeys = Object.keys(contractParams[name])
      const omitted = contractKeys.filter((k) => !zodKeys.has(k)).sort()
      expect(omitted, name).toEqual((UI_OMITTED[name] ?? []).slice().sort())
    }
  })
})
