-- Baseline (7/7): scheduled purge (platform-only).
--
-- Requires the pg_cron extension, which exists on the managed platform but not on
-- a stock Postgres. This file is intentionally separate so the schema-equivalence
-- check can replay 0001-0006 on a throwaway database; cron objects live outside
-- the public schema and are not part of that comparison.
--
-- Hourly job: drop analysis runs past their retention window.

create extension if not exists pg_cron;

select cron.schedule(
    'purge-expired-analysis-runs',
    '0 * * * *',
    $$delete from analysis_runs where expires_at is not null and expires_at < now()$$
);
