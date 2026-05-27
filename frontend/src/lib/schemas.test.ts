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
} from './schemas'

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
