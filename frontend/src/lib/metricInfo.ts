/**
 * metricInfo: the single home for the plain-language definitions shown in the
 * info tooltips across the stage result views.
 *
 * Both column headers (via a column's `meta.info`) and summary cards (via the
 * `StageSummaryCard` `info` prop) read their copy from this map, so every metric
 * a user sees has one canonical definition and edits happen in one file.
 *
 * Copy rules: plain language, scientifically accurate, no em dashes, and no
 * internal project vocabulary. Keys are namespaced by the stage they belong to
 * (s2 = drug-likeness screen, s3 = compound-target lookup, s4 = disease targets,
 * s5 = shared-target overlap, s6 = interaction network, s7 = hub ranking,
 * s8 = functional enrichment). `common` holds definitions shared across stages.
 */
export const METRIC_INFO = {
  // --- Shared across stages (identifiers) ---
  common: {
    uniprot: "UniProt accession, the standard database identifier for a protein.",
    geneSymbol: "The human gene that codes for this protein.",
    inchikey:
      "A fixed-length code that uniquely identifies a chemical structure. Two molecules with the same structure always share the same InChIKey.",
    smiles:
      "A compact text notation that spells out a molecule's atoms and bonds as a single line of characters.",
  },

  // --- Drug-likeness screening (ADME) ---
  s2: {
    status:
      "Whether the compound cleared the drug-likeness screen (passed) or was excluded (filtered).",
    lipinski:
      "Whether the compound meets Lipinski's rule of five, a standard checklist of size, greasiness, and hydrogen bonding that most oral drugs satisfy.",
    veber:
      "Whether the compound passes Veber's rule, which favours oral drugs by limiting molecular flexibility and polar surface area.",
    npBypass:
      "The compound closely resembles known natural products, so it is allowed through even if it fails the drug-likeness rules.",
    mw: "Molecular weight in daltons, one of the four properties in Lipinski's rule of five.",
    logp: "Predicted fat versus water preference (logP). Higher means greasier. One of the four Lipinski properties.",
    hbd: "Number of hydrogen bond donors, one of the four Lipinski properties.",
    hba: "Number of hydrogen bond acceptors, one of the four Lipinski properties.",
    tpsa: "Topological polar surface area in square angstroms, a Veber property that estimates how easily the compound crosses membranes.",
    rotb: "Number of rotatable bonds, a Veber property that measures how flexible the molecule is.",
    npScore:
      "Natural-product likeness score. Higher means the structure more closely resembles known natural products. This is the value the natural-product exception is judged against.",
    pains:
      "A check means no pan-assay interference alert. A cross means the structure matches a pattern known to give misleading assay results. This only flags the compound and never filters it out.",
    unscreened:
      "Number of compounds that skipped the drug-likeness screen because screening was turned off for this run. They are counted as passed.",
  },

  // --- Compound-target bioactivity lookup ---
  s3: {
    coverage:
      "Share of the compounds that returned at least one protein target from the bioactivity databases.",
    chembl:
      "Number of compounds that returned target data from the ChEMBL bioactivity database.",
    pubchemBioassay:
      "Number of compounds that returned target data from the PubChem BioAssay database.",
  },

  // --- Disease target collection ---
  s4: {
    openTargetsScore:
      "Open Targets association score linking this protein to the disease. Higher means stronger published evidence.",
    minScore:
      "The lowest Open Targets association score a protein needed to be included. Proteins scoring below it were left out.",
  },

  // --- Shared-target overlap ---
  s5: {
    overlapTargets:
      "Proteins targeted by the compounds that are also linked to the disease. These shared targets are what the rest of the analysis builds on.",
    compoundSideTargets:
      "All proteins the compounds are predicted to act on, before intersecting with the disease.",
    diseaseSideTargets:
      "All proteins linked to the disease, before intersecting with the compound targets.",
  },

  // --- Protein interaction network (STRING) ---
  s6: {
    source: "One of the two proteins in this interaction.",
    target: "The other protein in this interaction.",
    confidence:
      "STRING's confidence that this interaction is real, from 0 to 1. Weaker links are not returned.",
    nodes: "Number of proteins placed in the interaction network.",
    edges: "Number of interactions STRING found among those proteins.",
    minConfidence: "The lowest STRING confidence score an interaction needed to be included.",
    networkType:
      "Which kind of STRING evidence was used, such as full functional associations or physical binding only.",
    unmapped:
      "Number of shared targets that have no gene symbol. Interactions are looked up by gene symbol, so these proteins cannot enter the network.",
  },

  // --- Hub gene ranking ---
  s7: {
    rank: "Position in the hub ranking, where 1 is the most central protein. Ties are broken by clique score, then by number of connections.",
    mcc: "Maximal Clique Centrality (Chin 2014). Scores a protein by how often it sits inside tightly interconnected clusters. This is the score the ranking uses.",
    degree:
      "Degree centrality: the share of all other proteins in the network that this one directly interacts with, scaled from 0 to 1.",
    betweenness:
      "Betweenness centrality: how often this protein sits on the shortest path between two others. High values act as bridges in the network.",
    closeness:
      "Closeness centrality: how short this protein's average path is to every other protein. Higher means more central.",
    eigenvector:
      "Eigenvector centrality: influence that counts not just how many proteins this one connects to, but how well connected those neighbours are.",
    networkNodes: "Number of proteins in the interaction network this ranking was computed over.",
    hubsReported:
      "Number of top-ranked proteins shown, set by the run's top-N setting or the whole network if it is smaller.",
    rankingMetric: "The scoring method used to rank hubs. Here it is Maximal Clique Centrality.",
  },

  // --- Functional enrichment ---
  s8: {
    category:
      "Which database this term comes from: biological process, molecular function, cellular component, or KEGG pathway.",
    term: "The term's own identifier in its source database.",
    correctedP:
      "Statistical significance after correcting for testing many terms at once. Lower means the overlap is less likely to be chance.",
    termSize: "Total number of genes assigned to this term across the whole background gene set.",
    overlap: "How many of the query genes fall within this term.",
    genes: "The query genes that belong to this term.",
    enrichedTerms:
      "Number of biological terms and pathways that passed both the significance threshold and the minimum term size.",
    queryGenes: "Number of distinct shared-target genes submitted for enrichment testing.",
    backgroundGenes:
      "Number of genes used as the comparison set. This run uses the compound-target genes rather than the whole genome.",
    correction:
      "The method used to adjust significance for testing many terms at once, so a few false positives do not slip through.",
  },
} as const;
