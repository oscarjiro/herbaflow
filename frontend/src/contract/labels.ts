export const INPUT_MODE_DESCRIPTIONS: Record<string, string> = {
  selection: "Pick plants from the catalogue; their compounds seed the pipeline.",
  disease_selection: "Pick a disease from the catalogue; its associated targets seed the pipeline.",
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
  "ADME screening",
  "Compound targets",
  "Disease targets",
  "Target overlap",
  "PPI network",
  "Hub genes",
  "Functional enrichment",
] as const;

export function stageLabel(n: number): string {
  return STAGE_LABELS[n - 1] ?? `Step ${n}`;
}

// Short one-line subtitle shown under each stage view's title. Deliberately terse
// (the landing WorkflowTimeline keeps its own fuller prose); this is the in-app
// at-a-glance line that replaces the old number+title redundancy in the header.
export const STAGE_DESCRIPTIONS = [
  "Bioactive compounds reported for the selected plant",
  "Druglikeness screening by Lipinski and Veber rules",
  "Human proteins each compound is measured to act on",
  "Human proteins associated with the disease, by evidence strength",
  "Proteins where compound reach and disease biology overlap",
  "How the shared proteins interact, drawn from STRING",
  "The most central proteins, ranked by maximal clique centrality",
  "Biological processes and pathways the network reflects",
] as const;

export function stageDescription(n: number): string {
  return STAGE_DESCRIPTIONS[n - 1] ?? "";
}

// Human-readable param labels. The long help text shown in each param's info
// tooltip is contract-owned (shared/contracts/analysis.json `description`); the
// notes below record the external-API source each description was verified
// against so the wording stays scientifically accurate.
//
//   min_pchembl          ChEMBL pChEMBL = −log10(molar IC50/Ki/Kd/EC50/etc.);
//                        5 ≈ 10 µM, 6 = 1 µM, 7 = 100 nM. Verified: ChEMBL FAQ
//                        (chembl.gitbook.io chembl-data-questions).
//   min_assay_confidence ChEMBL target-confidence score 0–9; 9 = direct single
//                        protein, 7 = direct protein-complex subunits, <4 =
//                        non-protein/cellular. Verified: ChEMBL FAQ.
//   min_confidence       STRING combined-score floor (raw API 0–1000; contract
//                        uses the 0–1 fraction, tiers 0.15/0.4/0.7/0.9, default
//                        0.4 = medium). Verified: STRING API help (string-db.org/help/api).
//   network_type         STRING functional (all association evidence) vs
//                        physical (binding only). Verified: STRING API help.
//   correction           g:Profiler multiple-testing method: g_SCS (default),
//                        fdr, bonferroni. Verified: g:Profiler gOSt API
//                        (biit.cs.ut.ee/gprofiler/page/apis).
//   no_iea               g:Profiler: exclude GO terms supported only by
//                        electronic (IEA) annotation. Verified: g:Profiler gOSt API.
//   significance_threshold g:Profiler user_threshold; corrected-p cutoff, float
//                        0–1. Verified: g:Profiler gOSt API.
//   min_term_size        g:Profiler: drop annotation terms smaller than this.
//                        g:Profiler-side term-size filter (standard g:GOSt option).
//   min_score            Open Targets overall disease-target association score,
//                        harmonic-sum heuristic bounded 0–1. Verified: Open
//                        Targets docs (platform-docs.opentargets.org/associations).
const LABELS: Record<string, string> = {
  // ADME screening (Stage 2)
  max_mw: "Max molecular weight (Da)",
  max_logp: "Max logP",
  max_hbd: "Max hydrogen-bond donors",
  max_hba: "Max hydrogen-bond acceptors",
  max_tpsa: "Max polar surface area (Å²)",
  max_rotatable_bonds: "Max rotatable bonds",
  np_exception_threshold: "Natural-product exception threshold",
  max_violations: "Max rule violations allowed",
  apply_veber: "Apply Veber rule",
  apply_np_exception: "Allow natural-product exceptions",
  skip_adme: "Skip druglikeness filtering",
  // Compound targets (Stage 3)
  min_pchembl: "Minimum activity (pChEMBL)",
  min_assay_confidence: "Minimum assay confidence",
  // Disease targets (Stage 4)
  min_score: "Minimum score",
  // PPI network (Stage 6)
  min_confidence: "Minimum confidence",
  network_type: "Network type",
  // Hub genes (Stage 7)
  top_n: "Top N",
  // Functional enrichment (Stage 8)
  min_term_size: "Minimum term size",
  significance_threshold: "Significance threshold (corrected p ≤)",
  correction: "Correction",
  no_iea: "Exclude electronic annotations (IEA)",
  sources: "Annotation sources",
};

const VALUES: Record<string, string> = {
  mcc: "MCC",
  functional: "Functional association",
  physical: "Physical interaction",
  g_SCS: "g:SCS",
  fdr: "Benjamini-Hochberg FDR",
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

// Compact forms for narrow stat-card display where the full humanized phrase
// would wrap awkwardly in a tile (the full name stays available via tooltip).
const VALUE_SHORT: Record<string, string> = {
  fdr: "BH-FDR",
};

export function humanizeValueShort(value: string): string {
  return VALUE_SHORT[value] ?? humanizeValue(value);
}
