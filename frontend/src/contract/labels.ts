export const INPUT_MODE_DESCRIPTIONS: Record<string, string> = {
  selection: "Pick plants from the catalogue; their compounds seed the pipeline.",
  manual_compounds: "Paste compound identifiers directly instead of picking plants.",
  manual_targets: "Paste protein targets directly and skip compound discovery.",
  manual_disease_targets: "Paste disease-associated targets directly instead of picking a disease.",
};

export const ENRICHMENT_SOURCE_LABELS: Record<string, string> = {
  "GO:BP": "Biological Process",
  "GO:MF": "Molecular Function",
  "GO:CC": "Cellular Component",
  KEGG: "KEGG Pathway",
  REAC: "Reactome Pathway",
  WP: "WikiPathways",
};

export const STAGE_LABELS = [
  "Compounds",
  "Druglikeness",
  "Compound targets",
  "Disease targets",
  "Shared targets",
  "Interaction network",
  "Hub genes",
  "Pathway enrichment",
] as const;

export function stageLabel(n: number): string {
  return STAGE_LABELS[n - 1] ?? `Step ${n}`;
}

const LABELS: Record<string, string> = {
  min_term_size: "Minimum term size",
  significance_threshold: "Significance threshold (corrected p ≤)",
  correction: "Correction",
  network_type: "Network type",
  top_n: "Top N",
  min_confidence: "Minimum confidence",
  min_score: "Minimum score",
  no_iea: "Exclude electronic annotations (IEA)",
};

const VALUES: Record<string, string> = {
  functional: "Functional",
  physical: "Physical",
  g_SCS: "g:SCS",
  fdr: "FDR",
  bonferroni: "Bonferroni",
  REAC: "Reactome",
  WP: "WikiPathways",
};

export function humanizeLabel(key: string): string {
  return LABELS[key] ?? key;
}

export function humanizeValue(value: string): string {
  return VALUES[value] ?? value;
}
