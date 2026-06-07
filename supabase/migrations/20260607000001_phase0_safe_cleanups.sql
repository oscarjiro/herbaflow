-- Safe, standalone cleanups. Idempotent where possible.

-- 1. Fast-purge index for the hourly pg_cron sweep + lazy-reaper on expires_at.
create index if not exists idx_analysis_runs_expires_at on public.analysis_runs (expires_at);

-- 2. Drop duplicate indexes on targets (gene_symbol and uniprot_accession were each
--    indexed twice: idx_targets_* and targets_*_idx). Keep the idx_targets_* names.
drop index if exists public.targets_gene_symbol_idx;
drop index if exists public.targets_uniprot_accession_idx;

-- 3. Delete the leftover test analysis runs (the rebuild starts from a clean slate).
delete from public.analysis_runs;
