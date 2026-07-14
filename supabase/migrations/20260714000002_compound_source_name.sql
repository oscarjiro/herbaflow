-- source_name: which upstream database anchored this compound's canonical structure/identity
-- (e.g. 'KNApSAcK World', 'PubChem'). Surfaced by Stage 1 so the per-run data-source panel lists
-- only the sources that actually contributed compounds this run. Display/provenance only, never
-- identity. Nullable (ETL name-only rows carry no external source attribution).
alter table public.compounds add column source_name text;
