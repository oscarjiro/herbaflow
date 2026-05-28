import { describe, it, expect } from 'vitest'
import { sourceUrls, enrichmentTermUrl } from '@/lib/sourceUrls'

describe('sourceUrls', () => {
  it('generates correct PubChem URL for numeric CID', () => {
    expect(sourceUrls.compound(123456)).toBe('https://pubchem.ncbi.nlm.nih.gov/compound/123456')
  })

  it('generates correct PubChem URL for string CID', () => {
    expect(sourceUrls.compound('5280343')).toBe('https://pubchem.ncbi.nlm.nih.gov/compound/5280343')
  })

  it('generates correct UniProt URL', () => {
    expect(sourceUrls.target('P12345')).toBe('https://www.uniprot.org/uniprotkb/P12345')
  })

  it('generates correct KNApSAcK URL', () => {
    expect(sourceUrls.plant('C00001234')).toBe('https://knapsack.nakatu.com/family.html?id=C00001234')
  })

  it('generates correct GO term URL', () => {
    expect(decodeURIComponent(sourceUrls.goTerm('GO:0008150'))).toBe('https://amigo.geneontology.org/amigo/term/GO:0008150')
  })

  it('generates correct KEGG URL', () => {
    expect(sourceUrls.kegg('hsa04151')).toBe('https://www.genome.jp/entry/hsa04151')
  })

  it('generates correct Reactome URL', () => {
    expect(sourceUrls.reactome('R-HSA-109581')).toBe('https://reactome.org/PathwayBrowser/#R-HSA-109581')
  })

  it('generates correct WikiPathways URL', () => {
    expect(sourceUrls.wikipathways('WP195')).toBe('https://www.wikipathways.org/pathways/WP195')
  })
})

describe('enrichmentTermUrl', () => {
  it('routes GO:BP terms to AmiGO', () => {
    expect(enrichmentTermUrl('GO:0008150', 'GO:BP')).toContain('amigo.geneontology.org')
  })

  it('routes GO:MF terms to AmiGO', () => {
    expect(enrichmentTermUrl('GO:0003674', 'GO:MF')).toContain('amigo.geneontology.org')
  })

  it('routes GO:CC terms to AmiGO', () => {
    expect(enrichmentTermUrl('GO:0005575', 'GO:CC')).toContain('amigo.geneontology.org')
  })

  it('routes KEGG correctly', () => {
    expect(enrichmentTermUrl('hsa04151', 'KEGG')).toContain('genome.jp')
  })

  it('routes Reactome correctly', () => {
    expect(enrichmentTermUrl('R-HSA-109581', 'Reactome')).toContain('reactome.org')
  })

  it('routes WikiPathways correctly (case-insensitive)', () => {
    expect(enrichmentTermUrl('WP195', 'WikiPathways')).toContain('wikipathways.org')
  })

  it('defaults unknown source to AmiGO', () => {
    expect(enrichmentTermUrl('GO:0001234', 'unknown')).toContain('amigo.geneontology.org')
  })

  it('includes the term ID in the URL', () => {
    const url = enrichmentTermUrl('GO:0008150', 'GO:BP')
    expect(decodeURIComponent(url)).toContain('GO:0008150')
  })
})
