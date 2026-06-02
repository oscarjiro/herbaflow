-- Alias hygiene + schema trim
--
-- Drops columns that no longer carry information:
--   * Alias tables replicated their parent entity's source provenance
--     (source_id / source_url) on every row — redundant, so removed.
--   * plants kept six GBIF join keys plus taxonomic_status/rank/authorship that
--     are never read by the API or UI (family_name is the only taxonomy field served).
--   * targets.organism_tax_id was a constant 9606 (all targets are human).
--   * compounds.lipinski_source held a single value or null and discriminated nothing.
--   * analysis_runs.notes / created_by were never written, read, or served.
--
-- 21 columns dropped total: 8 alias source + 9 plants + 1 targets + 1 compounds + 2 analysis_runs.
-- All use IF EXISTS so the migration is idempotent.

-- Alias source provenance (parent-inherited; redundant)
alter table plant_aliases
  drop column if exists source_id,
  drop column if exists source_url;
alter table compound_aliases
  drop column if exists source_id,
  drop column if exists source_url;
alter table target_aliases
  drop column if exists source_id,
  drop column if exists source_url;
alter table disease_aliases
  drop column if exists source_id,
  drop column if exists source_url;

-- plants: unused GBIF join keys + display-unused taxonomy fields (family_name kept)
alter table plants
  drop column if exists gbif_usage_key,
  drop column if exists gbif_accepted_usage_key,
  drop column if exists gbif_species_key,
  drop column if exists gbif_genus_key,
  drop column if exists gbif_family_key,
  drop column if exists gbif_kingdom_key,
  drop column if exists taxonomic_status,
  drop column if exists rank,
  drop column if exists authorship;

-- targets: constant 9606 (all targets human)
alter table targets
  drop column if exists organism_tax_id;

-- compounds: single-value/null provenance marker (no discrimination)
alter table compounds
  drop column if exists lipinski_source;

-- analysis_runs: dead columns (never written/read/served)
alter table analysis_runs
  drop column if exists notes,
  drop column if exists created_by;
