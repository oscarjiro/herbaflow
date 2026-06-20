-- Live per-item progress for long stages (ADME / target identification).
-- One row per run; a side table so progress writes never block on the run-row lock.
create table public.analysis_run_progress (
    analysis_id uuid primary key
        references public.analysis_runs(analysis_id) on delete cascade,
    stage integer not null,
    processed integer not null,
    total integer not null,
    updated_at timestamptz not null
);

alter table public.analysis_run_progress enable row level security;
