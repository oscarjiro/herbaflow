-- Add lipinski_source provenance column to compounds table.
-- Indicates how Lipinski/ADME descriptors were obtained:
--   chembl_api     — from ChEMBL molecule_properties (API)
--   rdkit_computed — computed from SMILES via RDKit (patch_missing_lipinski.py)
--   (empty)        — unresolved; no ChEMBL ID and no usable SMILES

alter table compounds
  add column if not exists lipinski_source text;
