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
  nestedParamsSchema,
  nestAdvancedParams,
  capState,
  manualFieldState,
  lineErrorsFor,
} from './schemas'
import { DEFAULT_PARAMS } from '@/components/setup/AdvancedParameters'

// A baseline nested params object that satisfies nestedParamsSchema; individual
// tests override single fields to assert bound-by-bound behaviour.
const VALID_PARAMS = nestAdvancedParams(DEFAULT_PARAMS)

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

describe('nestedParamsSchema — min_pchembl bounds', () => {
  it('accepts the baseline nested params object', () => {
    expect(nestedParamsSchema.safeParse(VALID_PARAMS).success).toBe(true)
  })

  it('rejects min_pchembl = 15 (backend allows ≤ 14)', () => {
    const bad = nestAdvancedParams({ ...DEFAULT_PARAMS, min_pchembl: 15 })
    const r = nestedParamsSchema.safeParse(bad)
    expect(r.success).toBe(false)
  })

  it('accepts min_pchembl = 14 (upper bound)', () => {
    const ok = nestAdvancedParams({ ...DEFAULT_PARAMS, min_pchembl: 14 })
    const r = nestedParamsSchema.safeParse(ok)
    expect(r.success).toBe(true)
  })
})

describe('nestedParamsSchema — min_confidence STRING presets', () => {
  it('accepts the 0.40 (Medium) preset', () => {
    const ok = nestAdvancedParams({ ...DEFAULT_PARAMS, min_confidence: 0.4 })
    const r = nestedParamsSchema.safeParse(ok)
    expect(r.success).toBe(true)
  })

  it.each([0.15, 0.4, 0.7, 0.9])('accepts STRING preset %s', (preset) => {
    const ok = nestAdvancedParams({ ...DEFAULT_PARAMS, min_confidence: preset })
    const r = nestedParamsSchema.safeParse(ok)
    expect(r.success).toBe(true)
  })

  it('rejects an off-preset confidence like 0.5', () => {
    const bad = nestAdvancedParams({ ...DEFAULT_PARAMS, min_confidence: 0.5 as never })
    const r = nestedParamsSchema.safeParse(bad)
    expect(r.success).toBe(false)
  })
})

// ---------------------------------------------------------------------------
// capState — UI cap/warn helper
// ---------------------------------------------------------------------------

describe('capState', () => {
  it('flags over the hard cap', () => {
    expect(capState(21, 10, 20)).toMatchObject({ over: true, warn: true })
  })
  it('warns between soft and hard', () => {
    expect(capState(12, 10, 20)).toMatchObject({ over: false, warn: true })
  })
  it('is clear below soft', () => {
    expect(capState(3, 10, 20)).toMatchObject({ over: false, warn: false })
  })
  it('labels n / hard', () => {
    expect(capState(3, 10, 20).label).toBe('3 / 20')
  })
})

// ---------------------------------------------------------------------------
// manualFieldState — maps a list length to textarea messaging
// ---------------------------------------------------------------------------

describe('manualFieldState', () => {
  it('returns only an error when over the hard cap', () => {
    const s = manualFieldState(21, 10, 20, 'item')
    expect(s.error).toBeTruthy()
    expect(s.count).toBeUndefined()
    expect(s.warning).toBeUndefined()
  })
  it('returns a warning (with n / hard) between soft and hard', () => {
    const s = manualFieldState(12, 10, 20, 'item')
    expect(s.warning).toMatch(/12 \/ 20/)
    expect(s.error).toBeUndefined()
  })
  it('returns a singular count for n = 1', () => {
    expect(manualFieldState(1, 10, 20, 'structure')).toEqual({ count: '1 structure entered' })
  })
  it('pluralises the noun for n > 1 below soft', () => {
    expect(manualFieldState(3, 10, 20, 'structure')).toEqual({ count: '3 structures entered' })
  })
  it('returns an empty object for n = 0', () => {
    expect(manualFieldState(0, 10, 20, 'structure')).toEqual({})
  })
})

// ---------------------------------------------------------------------------
// lineErrorsFor — per-line format hints for manual textarea inputs
// ---------------------------------------------------------------------------

describe('lineErrorsFor', () => {
  it('flags an invalid target line with a 1-based index', () => {
    const e = lineErrorsFor('target', ['TP53', 'bad!'])
    expect(e[2]).toMatch(/gene symbol or UniProt accession/i)
    expect(e[1]).toBeUndefined()
  })
  it('accepts a UniProt accession as a target', () => {
    expect(lineErrorsFor('target', ['P04637'])[1]).toBeUndefined()
  })
  it('flags too-short SMILES', () => {
    expect(lineErrorsFor('compound', ['CC', 'x'])[2]).toBeTruthy()
  })
  it('ignores blank lines (no error key, keeps 1-based alignment)', () => {
    const e = lineErrorsFor('target', ['TP53', '', 'bad!'])
    expect(e[2]).toBeUndefined()   // blank line is not flagged
    expect(e[3]).toMatch(/gene symbol or UniProt accession/i)
  })
})

