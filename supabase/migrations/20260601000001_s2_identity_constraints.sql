-- Identity unification: pair-grain bridges + alias natural keys.
-- Applied during the bundled reload (data is re-derived to conform first). Idempotent.
--
-- Bridges become one row per entity pair (source is an attribute, not part of the
-- key); aliases get a natural key of (parent_id, alias_key) so alias_type is a plain
-- attribute. See docs/database.md for the unified identity contract.

-- 1. Bridges: drop the old (left, right, source_id) UNIQUE -> UNIQUE(left, right) (pair grain).
alter table plant_compounds  drop constraint if exists plant_compounds_plant_id_compound_id_source_id_key;
alter table compound_targets drop constraint if exists compound_targets_compound_id_target_id_source_id_key;
alter table disease_targets  drop constraint if exists disease_targets_disease_id_target_id_source_id_key;

alter table plant_compounds  add constraint plant_compounds_pair_key   unique (plant_id, compound_id);
alter table compound_targets add constraint compound_targets_pair_key  unique (compound_id, target_id);
alter table disease_targets  add constraint disease_targets_pair_key   unique (disease_id, target_id);

-- 2. Alias natural keys (parent_id, alias_key).
alter table plant_aliases    add constraint plant_aliases_parent_key    unique (plant_id, alias_key);
alter table compound_aliases add constraint compound_aliases_parent_key unique (compound_id, alias_key);
alter table target_aliases   add constraint target_aliases_parent_key   unique (target_id, alias_key);
alter table disease_aliases  add constraint disease_aliases_parent_key  unique (disease_id, alias_key);

-- 3. Missing single-column index on disease_aliases(alias_key) (other 3 alias tables already have it).
create index if not exists idx_disease_aliases_alias_key on disease_aliases (alias_key);
