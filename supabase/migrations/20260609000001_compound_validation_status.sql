-- Adds compounds.validation_status (externally_validated | structure_only),
-- seeds a Manual Entry source system, and flips the analysis mode default to guided.

alter table public.compounds
    add column validation_status text not null default 'externally_validated';

alter table public.compounds
    add constraint compounds_validation_status_check
    check (validation_status in ('externally_validated', 'structure_only'));

insert into public.source_systems (source_id, source_name, source_type, base_url)
values (gen_random_uuid(), 'Manual Entry', 'manual', null)
on conflict (source_name) do nothing;

alter table public.analysis_runs alter column mode set default 'guided';
