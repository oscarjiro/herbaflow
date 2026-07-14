-- connectivity_key: tautomer-canonical InChIKey skeleton (first 14 chars). Used only for cross-database
-- (ChEMBL/PubChem) connectivity matching in Stage 3, never as identity. Nullable.
alter table public.compounds add column connectivity_key text;
create index if not exists compounds_connectivity_key_idx on public.compounds (connectivity_key);

-- Widen validation_status: ETL structure-anchored rows that fail corroboration (name-only, no
-- structure) are not 'externally_validated'. Add a third honest value.
alter table public.compounds drop constraint compounds_validation_status_check;
alter table public.compounds add constraint compounds_validation_status_check
    check (validation_status in ('externally_validated', 'structure_only', 'unvalidated'));
