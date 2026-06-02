-- Type tightening + value constraints. Authored during the data-integrity rebuild.
--
-- IMPORTANT: apply against EMPTY tables (post-truncate, pre-load) at the bundled reload.
-- The text->uuid casts, the NOT NULL, and the CHECKs assume conforming (or zero) rows;
-- legacy pre-reload ids may not cast to uuid.

begin;

-- ============================================================
-- 1. Entity *_id + FK columns: text -> uuid (kills the text/uuid asymmetry).
--    Drop FKs -> alter column types -> re-add FKs.
-- ============================================================

-- 1a. Drop FK constraints referencing the entity PKs.
alter table plant_aliases    drop constraint if exists plant_aliases_plant_id_fkey;
alter table plant_compounds  drop constraint if exists plant_compounds_plant_id_fkey;
alter table plant_compounds  drop constraint if exists plant_compounds_compound_id_fkey;
alter table compound_aliases drop constraint if exists compound_aliases_compound_id_fkey;
alter table compound_targets drop constraint if exists compound_targets_compound_id_fkey;
alter table compound_targets drop constraint if exists compound_targets_target_id_fkey;
alter table target_aliases   drop constraint if exists target_aliases_target_id_fkey;
alter table disease_aliases  drop constraint if exists disease_aliases_disease_id_fkey;
alter table disease_targets  drop constraint if exists disease_targets_disease_id_fkey;
alter table disease_targets  drop constraint if exists disease_targets_target_id_fkey;
alter table analysis_runs    drop constraint if exists analysis_runs_disease_id_fkey;

-- 1b. Alter PK + FK + bridge/alias PK columns to uuid.
alter table plants           alter column plant_id           type uuid using plant_id::uuid;
alter table plant_aliases    alter column alias_id           type uuid using alias_id::uuid;
alter table plant_aliases    alter column plant_id           type uuid using plant_id::uuid;
alter table compounds        alter column compound_id        type uuid using compound_id::uuid;
alter table compound_aliases alter column compound_alias_id  type uuid using compound_alias_id::uuid;
alter table compound_aliases alter column compound_id        type uuid using compound_id::uuid;
alter table plant_compounds  alter column plant_compound_id  type uuid using plant_compound_id::uuid;
alter table plant_compounds  alter column plant_id           type uuid using plant_id::uuid;
alter table plant_compounds  alter column compound_id        type uuid using compound_id::uuid;
alter table targets          alter column target_id          type uuid using target_id::uuid;
alter table target_aliases   alter column target_alias_id    type uuid using target_alias_id::uuid;
alter table target_aliases   alter column target_id          type uuid using target_id::uuid;
alter table compound_targets alter column compound_target_id type uuid using compound_target_id::uuid;
alter table compound_targets alter column compound_id        type uuid using compound_id::uuid;
alter table compound_targets alter column target_id          type uuid using target_id::uuid;
alter table diseases         alter column disease_id         type uuid using disease_id::uuid;
alter table disease_aliases  alter column disease_alias_id   type uuid using disease_alias_id::uuid;
alter table disease_aliases  alter column disease_id         type uuid using disease_id::uuid;
alter table disease_targets  alter column disease_target_id  type uuid using disease_target_id::uuid;
alter table disease_targets  alter column disease_id         type uuid using disease_id::uuid;
alter table disease_targets  alter column target_id          type uuid using target_id::uuid;
alter table analysis_runs    alter column disease_id         type uuid using disease_id::uuid;

-- 1c. Re-add FK constraints (uuid -> uuid).
alter table plant_aliases    add constraint plant_aliases_plant_id_fkey       foreign key (plant_id)    references plants(plant_id);
alter table plant_compounds  add constraint plant_compounds_plant_id_fkey     foreign key (plant_id)    references plants(plant_id);
alter table plant_compounds  add constraint plant_compounds_compound_id_fkey  foreign key (compound_id) references compounds(compound_id);
alter table compound_aliases add constraint compound_aliases_compound_id_fkey foreign key (compound_id) references compounds(compound_id);
alter table compound_targets add constraint compound_targets_compound_id_fkey foreign key (compound_id) references compounds(compound_id);
alter table compound_targets add constraint compound_targets_target_id_fkey   foreign key (target_id)   references targets(target_id);
alter table target_aliases   add constraint target_aliases_target_id_fkey     foreign key (target_id)   references targets(target_id);
alter table disease_aliases  add constraint disease_aliases_disease_id_fkey   foreign key (disease_id)  references diseases(disease_id);
alter table disease_targets  add constraint disease_targets_disease_id_fkey   foreign key (disease_id)  references diseases(disease_id);
alter table disease_targets  add constraint disease_targets_target_id_fkey    foreign key (target_id)   references targets(target_id);
alter table analysis_runs    add constraint analysis_runs_disease_id_fkey     foreign key (disease_id)  references diseases(disease_id);

-- ============================================================
-- 2. Control-only vocab CHECKs (only columns our own code sets).
-- ============================================================
alter table compounds        add constraint compounds_lipinski_source_check
  check (lipinski_source is null or lipinski_source in ('chembl_api','rdkit_computed','rdkit_computed+rdkit_np','chembl_api+rdkit_np','rdkit_np'));
alter table compound_targets add constraint compound_targets_prediction_method_check
  check (prediction_method is null or prediction_method in ('chembl_bioactivity','pubchem_bioassay','stp_import'));
-- NOTE: analysis_runs.status is a dynamic, stage-derived string the backend manages
-- (pending/failed/complete plus stage_{N}_running / stage_{N}_awaiting_approval /
-- stage_{N}_starting / stage_{N}_rejected). It is not a fixed control vocab, so no
-- IN (...) CHECK is enforced on it.
alter table analysis_runs    add constraint analysis_runs_mode_check
  check (mode in ('auto','guided'));

-- ============================================================
-- 3. Numeric range CHECKs.
-- ============================================================
alter table compounds     add constraint compounds_num_ro5_violations_check
  check (num_ro5_violations is null or num_ro5_violations between 0 and 4);
alter table analysis_runs add constraint analysis_runs_current_stage_check
  check (current_stage is null or current_stage between 1 and 8);

-- ============================================================
-- 4. JSONB minimum (object-ness); deep shape stays in the app (Pydantic <-> Zod).
-- ============================================================
alter table analysis_runs alter column parameters set not null;
alter table analysis_runs add constraint analysis_runs_parameters_object_check
  check (jsonb_typeof(parameters) = 'object');
alter table analysis_runs add constraint analysis_runs_stage_results_object_check
  check (jsonb_typeof(stage_results) = 'object');

commit;
