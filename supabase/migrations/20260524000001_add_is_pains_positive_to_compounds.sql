-- Add PAINS flag to compounds table
-- PAINS (Pan-Assay Interference Compounds) flags structural patterns that cause
-- false positives in biochemical assays (Baell & Holloway, J. Med. Chem. 53:2719-2740, 2010).
-- Used for reporting only — not a hard filter in the computational pipeline.
-- Populated by ETL patch_missing_lipinski.py (Pass 3) on next ETL re-run.
ALTER TABLE compounds ADD COLUMN IF NOT EXISTS is_pains_positive boolean NOT NULL DEFAULT false;
