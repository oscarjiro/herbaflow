-- Drop tables that are never written to by any ETL or backend code.
-- Removal order respects FK dependencies.

-- 1. validation_reports references import_batches — drop first
drop table if exists validation_reports;

-- 2. No dependents on these
drop table if exists stg_plants;
drop table if exists stg_plant_compounds;
drop table if exists api_cache;

-- 3. Remove source_snapshot_id FK columns before dropping source_snapshots
--    (import_batches and ppi_edges both reference it; column is always null)
alter table import_batches drop column if exists source_snapshot_id;
alter table ppi_edges      drop column if exists source_snapshot_id;

-- 4. Now safe to drop
drop table if exists source_snapshots;
