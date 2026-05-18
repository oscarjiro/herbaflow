-- pChEMBL = -log10(IC50 in molar). Value >= 5 means IC50 <= 10uM (active).
-- Null for STITCH-sourced targets that don't have pChEMBL data.

ALTER TABLE compound_targets
  ADD COLUMN IF NOT EXISTS pchembl_value float;
