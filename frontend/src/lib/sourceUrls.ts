/**
 * External source URL helpers for entity links.
 * All links open in a new tab with noopener noreferrer.
 */

export const sourceUrls = {
  plant: (knapsackId: string) =>
    `https://knapsack.nakatu.com/family.html?id=${encodeURIComponent(knapsackId)}`,

  compound: (pubchemCid: string | number) =>
    `https://pubchem.ncbi.nlm.nih.gov/compound/${encodeURIComponent(pubchemCid)}`,

  target: (uniprotAccession: string) =>
    `https://www.uniprot.org/uniprotkb/${encodeURIComponent(uniprotAccession)}`,

  goTerm: (termId: string) =>
    `https://amigo.geneontology.org/amigo/term/${encodeURIComponent(termId)}`,

  kegg: (termId: string) =>
    `https://www.genome.jp/entry/${encodeURIComponent(termId)}`,

  reactome: (termId: string) =>
    `https://reactome.org/PathwayBrowser/#${encodeURIComponent(termId)}`,

  wikipathways: (termId: string) =>
    `https://www.wikipathways.org/pathways/${encodeURIComponent(termId)}`,
} as const

/** Detect which sourceUrls function to call based on term source */
export function enrichmentTermUrl(termId: string, source: string): string {
  const s = source.toLowerCase()
  if (s === 'kegg') return sourceUrls.kegg(termId)
  if (s === 'reactome') return sourceUrls.reactome(termId)
  if (s.includes('wiki')) return sourceUrls.wikipathways(termId)
  // Default: GO term (go_bp, go_mf, go_cc, GO:BP, GO:MF, GO:CC)
  return sourceUrls.goTerm(termId)
}
