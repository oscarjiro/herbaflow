import { describe, it, expect } from 'vitest'
import { parseSTPCsv, generateSTPExportCsv } from './stp'
import type { UncoveredCompound } from '@/types/api'

const SAMPLE_STP_CSV = `Target,Uniprot,Common name,Gene name,ChEMBL preferred compound,Probability,Known actives (3D),Known actives (2D)
Carbonic anhydrase I,P00915,CA1,CA1,CHEMBL104,0.43,0,5
Epidermal growth factor receptor,P00533,EGFR,EGFR,CHEMBL203,0.12,2,8
Albumin,P02768,ALB,ALB,CHEMBL2095,0.04,0,1`

const SAMPLE_STP_TSV = `Target\tUniprot\tCommon name\tGene name\tChEMBL preferred compound\tProbability\tKnown actives (3D)\tKnown actives (2D)
Carbonic anhydrase I\tP00915\tCA1\tCA1\tCHEMBL104\t0.43\t0\t5
Epidermal growth factor receptor\tP00533\tEGFR\tEGFR\tCHEMBL203\t0.12\t2\t8`

const SAMPLE_STP_CSV_WITH_QUOTED_TARGET = `Target,Uniprot,Common name,Gene name,ChEMBL preferred compound,Probability,Known actives (3D),Known actives (2D)
"Carbonic anhydrase, isoform I",P00915,CA1,CA1,CHEMBL104,0.43,0,5
Epidermal growth factor receptor,P00533,EGFR,EGFR,CHEMBL203,0.12,2,8`

describe('parseSTPCsv', () => {
  it('parses comma-separated STP output and filters by probability', () => {
    const result = parseSTPCsv(SAMPLE_STP_CSV, 0.1)
    expect(result.error).toBeNull()
    expect(result.targets).toHaveLength(2) // ALB filtered out (0.04 < 0.1)
    expect(result.targets[0]).toEqual({ uniprot_id: 'P00915', gene_symbol: 'CA1', probability: 0.43 })
    expect(result.targets[1]).toEqual({ uniprot_id: 'P00533', gene_symbol: 'EGFR', probability: 0.12 })
  })

  it('parses tab-separated STP output', () => {
    const result = parseSTPCsv(SAMPLE_STP_TSV, 0.1)
    expect(result.error).toBeNull()
    expect(result.targets).toHaveLength(2)
  })

  it('returns error for unrecognized format', () => {
    const result = parseSTPCsv('col1,col2,col3\nval1,val2,val3', 0.1)
    expect(result.error).toMatch(/Unrecognized format/)
    expect(result.targets).toHaveLength(0)
  })

  it('returns error for empty input', () => {
    const result = parseSTPCsv('', 0.1)
    expect(result.error).not.toBeNull()
    expect(result.targets).toHaveLength(0)
  })

  it('filters all targets when minProbability is 1.0', () => {
    const result = parseSTPCsv(SAMPLE_STP_CSV, 1.0)
    expect(result.error).toBeNull()
    expect(result.targets).toHaveLength(0)
  })

  it('parses CSV with quoted target names containing commas', () => {
    const result = parseSTPCsv(SAMPLE_STP_CSV_WITH_QUOTED_TARGET, 0.1)
    expect(result.error).toBeNull()
    expect(result.targets).toHaveLength(2)
    expect(result.targets[0].uniprot_id).toBe('P00915')
    expect(result.targets[0].gene_symbol).toBe('CA1')
    expect(result.targets[0].probability).toBe(0.43)
  })
})

describe('generateSTPExportCsv', () => {
  const compounds: UncoveredCompound[] = [
    { compound_id: 'cid-1', canonical_name: 'Quercetin', smiles: 'OC1=CC=CC=C1' },
    { compound_id: 'cid-2', canonical_name: 'Has "quotes"', smiles: 'CC' },
    { compound_id: 'cid-3', canonical_name: 'No SMILES', smiles: null },
  ]

  it('generates CSV with header and only smiles-bearing compounds', () => {
    const csv = generateSTPExportCsv(compounds)
    const lines = csv.split('\n')
    expect(lines[0]).toBe('compound_name,smiles')
    expect(lines).toHaveLength(3) // header + 2 compounds (null smiles excluded)
  })

  it('escapes double quotes in compound names', () => {
    const csv = generateSTPExportCsv(compounds)
    expect(csv).toContain('"Has ""quotes"""')
  })

  it('returns header-only CSV when all compounds lack SMILES', () => {
    const result = generateSTPExportCsv([
      { compound_id: 'x', canonical_name: 'No SMILES', smiles: null },
    ])
    expect(result.trim()).toBe('compound_name,smiles')
  })

  it('does not quote the SMILES column', () => {
    const csv = generateSTPExportCsv([
      { compound_id: 'cid-1', canonical_name: 'Quercetin', smiles: 'OC1=CC=CC=C1' },
    ])
    // SMILES must be unquoted — STP input format requires plain SMILES strings
    expect(csv).toContain(',OC1=CC=CC=C1')
    expect(csv).not.toContain(',"OC1=CC=CC=C1"')
  })
})
