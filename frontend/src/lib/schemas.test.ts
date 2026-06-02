/**
 * Unit tests for format-validation schemas in schemas.ts.
 *
 * Covers UniProt accession, HGNC gene symbol, and SMILES minimum validation —
 * mirroring the Pydantic validators in backend/app/schemas/analysis.py.
 */
import { describe, it, expect } from 'vitest'
import {
  uniprotAccessionSchema,
  geneSymbolSchema,
  smilesSchema,
  advancedParamsSchema,
} from './schemas'

// A baseline params object that satisfies advancedParamsSchema; individual
// tests override single fields to assert bound-by-bound behaviour.
const VALID_PARAMS = {
  max_mw: 500,
  max_logp: 5,
  max_hbd: 5,
  max_hba: 10,
  max_tpsa: 140,
  max_rotatable_bonds: 10,
  apply_veber: true,
  np_exception_threshold: 0.5,
  apply_adme_to_manual: true,
  min_pchembl: 5,
  human_only: true,
  min_assay_confidence: 7,
  min_score: 0.3,
  min_confidence: 0.4,
  top_n: 20,
  use_hub_bottleneck: true,
  fdr_threshold: 0.05,
  sources: ['GO:BP'],
}

// ---------------------------------------------------------------------------
// UniProt accession format
// ---------------------------------------------------------------------------

describe('uniprotAccessionSchema', () => {
  it('accepts valid P04637 (TP53 human)', () => {
    expect(uniprotAccessionSchema.safeParse('P04637').success).toBe(true)
  })

  it('accepts valid Q9Y6I3', () => {
    expect(uniprotAccessionSchema.safeParse('Q9Y6I3').success).toBe(true)
  })

  it('accepts valid O60341', () => {
    expect(uniprotAccessionSchema.safeParse('O60341').success).toBe(true)
  })

  it('rejects 123ABC (starts with digit)', () => {
    expect(uniprotAccessionSchema.safeParse('123ABC').success).toBe(false)
  })

  it('rejects gene_name (underscore, not an accession)', () => {
    expect(uniprotAccessionSchema.safeParse('gene_name').success).toBe(false)
  })

  it('rejects P1234 (too short, only 5 chars)', () => {
    expect(uniprotAccessionSchema.safeParse('P1234').success).toBe(false)
  })

  it('rejects p04637 (lowercase first letter)', () => {
    expect(uniprotAccessionSchema.safeParse('p04637').success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// HGNC gene symbol
// ---------------------------------------------------------------------------

describe('geneSymbolSchema', () => {
  it('accepts TP53', () => {
    expect(geneSymbolSchema.safeParse('TP53').success).toBe(true)
  })

  it('accepts EGFR', () => {
    expect(geneSymbolSchema.safeParse('EGFR').success).toBe(true)
  })

  it('accepts BRCA1', () => {
    expect(geneSymbolSchema.safeParse('BRCA1').success).toBe(true)
  })

  it('accepts HIF-1A (hyphen allowed)', () => {
    expect(geneSymbolSchema.safeParse('HIF-1A').success).toBe(true)
  })

  it('accepts HLA-A', () => {
    expect(geneSymbolSchema.safeParse('HLA-A').success).toBe(true)
  })

  it('rejects tp53 (lowercase)', () => {
    expect(geneSymbolSchema.safeParse('tp53').success).toBe(false)
  })

  it('rejects gene_lowercase (underscore + lowercase)', () => {
    expect(geneSymbolSchema.safeParse('gene_lowercase').success).toBe(false)
  })

  it('rejects 1BADSTART (starts with digit)', () => {
    expect(geneSymbolSchema.safeParse('1BADSTART').success).toBe(false)
  })

  it('rejects empty string', () => {
    expect(geneSymbolSchema.safeParse('').success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// SMILES minimum validation
// ---------------------------------------------------------------------------

describe('smilesSchema', () => {
  it('accepts CCO (ethanol, minimal valid SMILES)', () => {
    expect(smilesSchema.safeParse('CCO').success).toBe(true)
  })

  it('accepts c1ccccc1 (benzene)', () => {
    expect(smilesSchema.safeParse('c1ccccc1').success).toBe(true)
  })

  it('accepts aspirin SMILES', () => {
    expect(smilesSchema.safeParse('CC(=O)Oc1ccccc1C(=O)O').success).toBe(true)
  })

  it('rejects empty string (too short)', () => {
    expect(smilesSchema.safeParse('').success).toBe(false)
  })

  it('rejects single char "C" (length < 3)', () => {
    expect(smilesSchema.safeParse('C').success).toBe(false)
  })

  it('rejects two chars "CC" (length < 3)', () => {
    expect(smilesSchema.safeParse('CC').success).toBe(false)
  })

  it('rejects string with null byte (non-printable ASCII)', () => {
    expect(smilesSchema.safeParse('\x00toxic').success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// Advanced params bounds — mirror backend _validate_params in analysis.py
// ---------------------------------------------------------------------------

describe('advancedParamsSchema — min_pchembl bounds', () => {
  it('accepts the baseline params object', () => {
    expect(advancedParamsSchema.safeParse(VALID_PARAMS).success).toBe(true)
  })

  it('rejects min_pchembl = 15 (backend allows ≤ 14)', () => {
    const r = advancedParamsSchema.safeParse({ ...VALID_PARAMS, min_pchembl: 15 })
    expect(r.success).toBe(false)
  })

  it('accepts min_pchembl = 14 (upper bound)', () => {
    const r = advancedParamsSchema.safeParse({ ...VALID_PARAMS, min_pchembl: 14 })
    expect(r.success).toBe(true)
  })
})

describe('advancedParamsSchema — min_confidence STRING presets', () => {
  it('accepts the 0.40 (Medium) preset', () => {
    const r = advancedParamsSchema.safeParse({ ...VALID_PARAMS, min_confidence: 0.4 })
    expect(r.success).toBe(true)
  })

  it.each([0.15, 0.4, 0.7, 0.9])('accepts STRING preset %s', (preset) => {
    const r = advancedParamsSchema.safeParse({ ...VALID_PARAMS, min_confidence: preset })
    expect(r.success).toBe(true)
  })

  it('rejects an off-preset confidence like 0.5', () => {
    const r = advancedParamsSchema.safeParse({ ...VALID_PARAMS, min_confidence: 0.5 })
    expect(r.success).toBe(false)
  })
})

