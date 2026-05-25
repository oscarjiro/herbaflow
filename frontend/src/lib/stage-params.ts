/**
 * Shared stage parameter configuration.
 * Used by StageParamsPanel (in-stage rerun) and ApprovalBar (configure next stage).
 */

// Stage number → PipelineConfig key mapping
export const STAGE_PARAM_KEY: Record<number, string> = {
  2: 'adme',
  3: 'target',
  4: 'disease_targets',
  6: 'ppi',
  7: 'hub_genes',
  8: 'enrichment',
}

// Default values — must match backend analysis/models.py exactly
export const PARAM_DEFAULTS: Record<string, Record<string, unknown>> = {
  adme: {
    max_mw: 500,
    max_logp: 5.0,
    max_hbd: 5,
    max_hba: 10,
    max_tpsa: 140.0,
    max_rotatable_bonds: 10,
    apply_veber: true,
    apply_pains: false,
    np_exception_threshold: 0.5,
  },
  target: {
    min_pchembl: 5.0,
    human_only: true,
    min_assay_confidence: 7,
  },
  disease_targets: {
    min_score: 0.3,
  },
  ppi: {
    min_confidence: 0.4,
  },
  hub_genes: {
    top_n: 20,
    use_hub_bottleneck: true,
  },
  enrichment: {
    fdr_threshold: 0.05,
    sources: ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG'],
  },
}

// Human-readable labels for each param field
export const PARAM_LABELS: Record<string, Record<string, string>> = {
  adme: {
    max_mw: 'Max MW (Da)',
    max_logp: 'Max LogP',
    max_hbd: 'Max H-Bond Donors',
    max_hba: 'Max H-Bond Acceptors',
    max_tpsa: 'Max TPSA (Å²)',
    max_rotatable_bonds: 'Max Rotatable Bonds',
    apply_veber: 'Apply Veber Rules',
    apply_pains: 'Flag PAINS',
    np_exception_threshold: 'NP-likeness Threshold',
  },
  target: {
    min_pchembl: 'Min pChEMBL Value',
    human_only: 'Human Targets Only',
    min_assay_confidence: 'Min Assay Confidence (0–9)',
  },
  disease_targets: {
    min_score: 'Min Open Targets Score (0–1)',
  },
  ppi: {
    min_confidence: 'Min STRING Confidence (0–1)',
  },
  hub_genes: {
    top_n: 'Top N Hub Genes',
    use_hub_bottleneck: 'Hub+Bottleneck Composite',
  },
  enrichment: {
    fdr_threshold: 'FDR Threshold',
  },
}

// Numeric step values for number inputs
export const PARAM_STEP: Record<string, Record<string, number>> = {
  adme: {
    max_mw: 10,
    max_logp: 0.1,
    max_hbd: 1,
    max_hba: 1,
    max_tpsa: 5,
    max_rotatable_bonds: 1,
    np_exception_threshold: 0.05,
  },
  target: { min_pchembl: 0.5, min_assay_confidence: 1 },
  disease_targets: { min_score: 0.05 },
  ppi: { min_confidence: 0.05 },
  hub_genes: { top_n: 5 },
  enrichment: { fdr_threshold: 0.01 },
}

export const ENRICHMENT_SOURCES = ['GO:BP', 'GO:MF', 'GO:CC', 'KEGG']
