-- supabase/migrations/20260602000002_deep_link_provenance.sql
-- Per-row deep-link provenance: add source_url to link tables; drop the dead
-- import_batches table + source_batch_id columns. Applied during the one-time rebuild.

begin;

-- 1. Per-row source_url on the 3 link tables (entities/aliases already have it).
alter table plant_compounds  add column if not exists source_url text;
alter table compound_targets add column if not exists source_url text;
alter table disease_targets  add column if not exists source_url text;

-- 2. Drop source_batch_id (write-only batch FK) from all entity + alias tables.
alter table plants           drop column if exists source_batch_id;
alter table plant_aliases    drop column if exists source_batch_id;
alter table compounds        drop column if exists source_batch_id;
alter table compound_aliases drop column if exists source_batch_id;
alter table targets          drop column if exists source_batch_id;
alter table target_aliases   drop column if exists source_batch_id;
alter table diseases         drop column if exists source_batch_id;
alter table disease_aliases  drop column if exists source_batch_id;

-- 3. Drop the dead, write-only import_batches table.
drop table if exists import_batches cascade;

commit;
