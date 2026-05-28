/**
 * External source URL helpers for entity links.
 * All links open in a new tab with noopener noreferrer.
 */

export const sourceUrls = {
  plant: (knapsackId: string) =>
    `https://knapsack.nakatu.com/family.html?id=${knapsackId}`,

  compound: (pubchemCid: string | number) =>
    `https://pubchem.ncbi.nlm.nih.gov/compound/${pubchemCid}`,

  target: (uniprotAccession: string) =>
    `https://www.uniprot.org/uniprotkb/${uniprotAccession}`,

  goTerm: (termId: string) =>
    `https://amigo.geneontology.org/amigo/term/${termId}`,

  kegg: (termId: string) =>
    `https://www.genome.jp/entry/${termId}`,

  reactome: (termId: string) =>
    `https://reactome.org/PathwayBrowser/#${termId}`,

  wikpathways: (termId: string) =>
    `https://www.wikipathways.org/pathways/${termId}`,
} as const

/** Detect which sourceUrls function to call based on term source */
export function enrichmentTermUrl(termId: string, source: string): string {
  const s = source.toLowerCase()
  if (s === 'kegg') return sourceUrls.kegg(termId)
  if (s === 'reactome') return sourceUrls.reactome(termId)
  if (s.includes('wiki')) return sourceUrls.wikpathways(termId)
  // Default: GO term (go_bp, go_mf, go_cc, GO:BP, GO:MF, GO:CC)
  return sourceUrls.goTerm(termId)
}
