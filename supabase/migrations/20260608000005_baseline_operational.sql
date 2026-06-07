-- Baseline (5/7): operational tables.
--
-- source_systems is the provenance registry referenced by every entity and
-- junction. analysis_runs holds one pipeline run; its status column stays free
-- text (composite 'stage_{N}_{phase}'), while mode is constrained to the
-- analysis contract's vocabulary. The disease_id foreign key is added in 0006.

create table public.source_systems (
    source_id uuid default gen_random_uuid() not null,
    source_name text not null,
    source_type text not null,
    base_url text,
    notes text,
    constraint source_systems_pkey primary key (source_id),
    constraint source_systems_source_name_key unique (source_name),
    constraint source_systems_source_type_check check (source_type in ('scrape', 'api', 'download', 'manual'))
);

create table public.analysis_runs (
    analysis_id uuid default gen_random_uuid() not null,
    analysis_name text,
    disease_id uuid,
    parameters jsonb not null,
    status text,
    created_at timestamp with time zone,
    current_stage integer,
    stage_results jsonb default '{}'::jsonb not null,
    mode text default 'auto'::text not null,
    completed_at timestamp with time zone,
    error_message text,
    updated_at timestamp with time zone default now() not null,
    expires_at timestamp with time zone,
    constraint analysis_runs_pkey primary key (analysis_id),
    constraint analysis_runs_mode_check check (mode in ('auto', 'guided')),
    constraint analysis_runs_current_stage_check check (current_stage is null or (current_stage >= 1 and current_stage <= 8)),
    constraint analysis_runs_parameters_object_check check (jsonb_typeof(parameters) = 'object'),
    constraint analysis_runs_stage_results_object_check check (jsonb_typeof(stage_results) = 'object')
);
