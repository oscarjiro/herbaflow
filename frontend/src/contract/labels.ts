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
};

export function humanizeLabel(key: string): string {
  return LABELS[key] ?? key;
}

export function humanizeValue(value: string): string {
  return VALUES[value] ?? value;
}
