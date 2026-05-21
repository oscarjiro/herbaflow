-- Adds guided-mode state columns to analysis_runs.
-- current_stage: 1-8, null = not started
-- stage_results: JSONB map {stage_1: {...}, stage_2: {...}} written by pipeline
-- mode: 'auto' (pipeline runs end-to-end) | 'guided' (pauses for approval per stage)

ALTER TABLE analysis_runs
  ADD COLUMN IF NOT EXISTS current_stage   integer,
  ADD COLUMN IF NOT EXISTS stage_results   jsonb        NOT NULL DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS mode            text         NOT NULL DEFAULT 'auto',
  ADD COLUMN IF NOT EXISTS completed_at    timestamptz,
  ADD COLUMN IF NOT EXISTS error_message   text,
  ADD COLUMN IF NOT EXISTS updated_at      timestamptz  NOT NULL DEFAULT now();

UPDATE analysis_runs SET updated_at = created_at WHERE updated_at IS NULL;
