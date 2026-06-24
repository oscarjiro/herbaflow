// ---------------------------------------------------------------------------
// External URL builders — one home for all external knowledge-base links.
// Reused by EntryOverflowDialog, per-stage tables, and any future surface.
// ---------------------------------------------------------------------------

/**
 * Returns the UniProt entry page for the given protein accession.
 * Canonical form: https://www.uniprot.org/uniprotkb/<accession>/entry
 */
export function uniprotUrl(accession: string): string {
  return `https://www.uniprot.org/uniprotkb/${encodeURIComponent(accession)}/entry`;
}

/**
 * Returns the PubChem compound entry page for a persisted compound CID.
 * Canonical form: https://pubchem.ncbi.nlm.nih.gov/compound/<cid>
 */
export function pubchemCompoundUrl(cid: string): string {
  return `https://pubchem.ncbi.nlm.nih.gov/compound/${encodeURIComponent(cid)}`;
}

/**
 * Derives the public term page URL for a g:Profiler enrichment term.
 *
 * Mirrors the backend `_term_url` in `app/pipeline/results_handoff.py`.
 * g:Profiler embeds the source as a prefix on non-GO ids (e.g. `KEGG:04020`); GO terms
 * use the full `GO:` id for QuickGO.
 *
 * Sources: GO:BP / GO:MF / GO:CC → QuickGO; KEGG → kegg.jp; REAC → Reactome; WP → WikiPathways.
 */
export function enrichmentTermUrl(source: string, termId: string): string {
  if (source.startsWith("GO")) {
    return `https://www.ebi.ac.uk/QuickGO/term/${termId}`;
  }
  const bare = termId.includes(":") ? termId.split(":").slice(1).join(":") : termId;
  if (source === "KEGG") return `https://www.kegg.jp/entry/${bare}`;
  if (source === "REAC") return `https://reactome.org/content/detail/${bare}`;
  if (source === "WP") return `https://www.wikipathways.org/pathways/${bare}`;
  return "";
}
