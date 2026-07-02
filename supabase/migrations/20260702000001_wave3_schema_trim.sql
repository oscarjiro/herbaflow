-- Wave 3 schema trim. One atomic transaction. Trims the schema to the target ERD:
-- drops canonical_key / qed_score / source_id / idempotency_key, the four alias tables,
-- and source_systems; adds plants.gbif_key; hardens the natural keys.
--
-- gbif_key backfills from the existing canonical_key ('gbif:{key}') BEFORE canonical_key
-- is dropped; SET NOT NULL self-gates the 478/478 plant coverage (aborts + rolls back if
-- any plant lacks a gbif key).
--
-- Natural-key exception (live-DB verified 2026-07-02): inchi_key and uniprot_accession get
-- UNIQUE only and stay NULLABLE. Some entity classes genuinely have no such id: ChEMBL
-- biologics/inorganics have no computable InChIKey; non-coding-RNA targets have no UniProt
-- accession. Their '' sentinels are normalized to NULL first (Postgres UNIQUE permits
-- repeated NULLs), and two reviewed accessions the ETL name-match missed are backfilled.
--
-- if-exists guards on source_systems + the alias tables + source_id columns keep this
-- runnable against both the live DB (full schema) and the integration testcontainer, whose
-- baseline migration subset never created source_systems or the alias tables.
--
-- No explicit begin/commit: matches the repo migration convention (the caller's transaction
-- wraps the file — the integration harness's eng.begin() and Supabase apply_migration both do),
-- so a self-gating SET NOT NULL failure still rolls the whole migration back atomically.

-- gbif_key: add, backfill from canonical_key, harden
alter table public.plants add column gbif_key text;
update public.plants set gbif_key = substring(canonical_key from 6)
    where canonical_key like 'gbif:%';
alter table public.plants alter column gbif_key set not null;
alter table public.plants add constraint plants_gbif_key_key unique (gbif_key);

-- natural-key normalization + backfill (MUST run while canonical_key still exists)
update public.compounds set inchi_key = null where inchi_key = '';
update public.targets   set uniprot_accession = null where uniprot_accession = '';
update public.targets set uniprot_accession = 'Q9UBN1' where canonical_key = 'ensembl:ENSG00000075461';
update public.targets set uniprot_accession = 'C0HMD6' where canonical_key = 'ensembl:ENSG00000293685';

-- drop alias tables (their inbound FKs die with them)
drop table if exists public.plant_aliases;
drop table if exists public.compound_aliases;
drop table if exists public.target_aliases;
drop table if exists public.disease_aliases;

-- drop every source_id column (drops each *_source_id_fkey + its index where present)
alter table public.plants           drop column if exists source_id;
alter table public.compounds        drop column if exists source_id;
alter table public.targets          drop column if exists source_id;
alter table public.diseases         drop column if exists source_id;
alter table public.plant_compounds  drop column if exists source_id;
alter table public.compound_targets drop column if exists source_id;
alter table public.disease_targets  drop column if exists source_id;

-- drop source_systems (now unreferenced)
drop table if exists public.source_systems;

-- drop canonical_key (drops each *_canonical_key_key unique). AFTER the gbif + accession reads.
alter table public.plants    drop column canonical_key;
alter table public.compounds drop column canonical_key;
alter table public.targets   drop column canonical_key;
alter table public.diseases  drop column canonical_key;

-- drop qed_score
alter table public.compounds drop column qed_score;

-- drop idempotency_key (+ its partial unique index, dropped with the column)
alter table public.analysis_runs drop column idempotency_key;

-- natural-key hardening. inchi_key/uniprot_accession get UNIQUE ONLY (stay nullable);
-- ontology_id is clean -> NOT NULL + UNIQUE.
alter table public.compounds add constraint compounds_inchi_key_key unique (inchi_key);
alter table public.targets   add constraint targets_uniprot_accession_key unique (uniprot_accession);
alter table public.diseases  alter column ontology_id set not null;
alter table public.diseases  add constraint diseases_ontology_id_key unique (ontology_id);

-- other NOT NULLs
alter table public.analysis_runs    alter column status set not null;
alter table public.analysis_runs    alter column created_at set not null;
alter table public.diseases         alter column disease_name set not null;
alter table public.plants           alter column canonical_scientific_name set not null;
alter table public.compound_targets alter column prediction_method set not null;
