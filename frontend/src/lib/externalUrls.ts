// ---------------------------------------------------------------------------
// External URL builders — one home for all external knowledge-base links.
// Reused by EntryOverflowDialog, per-stage tables, and any future surface.
// ---------------------------------------------------------------------------

/**
 * Returns the PubChem compound page for the given InChIKey.
 * PubChem's canonical InChIKey landing: https://pubchem.ncbi.nlm.nih.gov/#query=<inchikey>
 */
export function pubchemUrl(inchikey: string): string {
  return `https://pubchem.ncbi.nlm.nih.gov/#query=${encodeURIComponent(inchikey)}`;
}

/**
 * Returns the UniProt entry page for the given protein accession.
 * Canonical form: https://www.uniprot.org/uniprotkb/<accession>/entry
 */
export function uniprotUrl(accession: string): string {
  return `https://www.uniprot.org/uniprotkb/${encodeURIComponent(accession)}/entry`;
}
