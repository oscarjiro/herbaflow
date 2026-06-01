-- Drop decorative/unused tables, columns, and redundant indexes; add TTL purge.
-- Applied during the one-time data rebuild.

begin;

-- 1. Drop unused derived + junction tables (no ORM model / writer / reader;
--    analysis serves entirely from analysis_runs.stage_results jsonb).
drop table if exists target_rankings cascade;
drop table if exists target_pathways cascade;
drop table if exists pathways cascade;
drop table if exists analysis_run_ppi_edges cascade;
drop table if exists ppi_edges cascade;
drop table if exists analysis_run_plants cascade;
drop table if exists analysis_run_compounds cascade;
drop table if exists analysis_run_targets cascade;
drop table if exists analysis_run_diseases cascade;

-- 2. Drop unread confidence column (kept score/association_type on links).
alter table plants           drop column if exists confidence;
alter table compounds        drop column if exists confidence;
alter table diseases         drop column if exists confidence;
alter table targets          drop column if exists confidence;
alter table plant_compounds  drop column if exists confidence;
alter table compound_targets drop column if exists confidence;
alter table disease_targets  drop column if exists confidence;

-- 3. Drop redundant evidence_type (prediction_method retained on compound_targets).
alter table plant_compounds  drop column if exists evidence_type;
alter table compound_targets drop column if exists evidence_type;

-- 4. Drop unused internal raw-record pointers on plant_compounds.
alter table plant_compounds  drop column if exists source_plant_raw_id;
alter table plant_compounds  drop column if exists source_compound_raw_id;

-- 5. Drop redundant canonical_key indexes (the unique constraint already builds an equivalent btree).
drop index if exists plants_canonical_key_idx;
drop index if exists compounds_canonical_key_idx;
drop index if exists targets_canonical_key_idx;
drop index if exists diseases_canonical_key_idx;

commit;

-- 6. Schedule ttl purge of expired analysis runs (pg_cron).
create extension if not exists pg_cron;
select cron.schedule(
    'purge-expired-analysis-runs',
    '0 * * * *',
    $$delete from analysis_runs where expires_at is not null and expires_at < now()$$
);
