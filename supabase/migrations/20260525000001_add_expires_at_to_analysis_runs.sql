-- T2.4: Add expires_at TTL column to analysis_runs.
-- Completed analyses expire 24h after completion; GET /analyses/{id} returns
-- 410 Gone once expired.

ALTER TABLE analysis_runs ADD COLUMN expires_at timestamptz;

-- Backfill: set expiry for runs that completed before this migration.
UPDATE analysis_runs
SET expires_at = completed_at + INTERVAL '24 hours'
WHERE status = 'complete'
  AND completed_at IS NOT NULL
  AND expires_at IS NULL;
