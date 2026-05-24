-- Frequently queried target lookup fields
CREATE INDEX IF NOT EXISTS idx_targets_uniprot_accession
  ON targets(uniprot_accession);

CREATE INDEX IF NOT EXISTS idx_targets_gene_symbol
  ON targets(gene_symbol);

-- Analysis status filtering (common in list queries)
CREATE INDEX IF NOT EXISTS idx_analysis_runs_status
  ON analysis_runs(status);

-- Disease-target score threshold filtering
CREATE INDEX IF NOT EXISTS idx_disease_targets_score
  ON disease_targets(score);
