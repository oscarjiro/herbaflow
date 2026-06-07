-- Baseline (2/7): entity tables.
--
-- The four canonical entities. Entity ids are UUID v5 values produced by the
-- application/ETL identity module (no database default). canonical_key is unique
-- per entity. Foreign keys to source_systems are added in 0006 (after all tables
-- exist), matching the create-tables-then-add-constraints baseline pattern.

create table public.plants (
    plant_id uuid not null,
    canonical_key text not null,
    canonical_scientific_name text,
    family_name text,
    source_id uuid,
    source_url text,
    retrieved_at timestamp with time zone,
    constraint plants_pkey primary key (plant_id),
    constraint plants_canonical_key_key unique (canonical_key)
);

create table public.compounds (
    compound_id uuid not null,
    canonical_key text not null,
    canonical_name text,
    inchi_key text,
    smiles text,
    cas_id text,
    pubchem_cid text,
    chembl_id text,
    molecular_formula text,
    molecular_weight double precision,
    tpsa double precision,
    logp double precision,
    hbond_donors integer,
    hbond_acceptors integer,
    rotatable_bonds integer,
    qed_score double precision,
    np_likeness_score double precision,
    num_ro5_violations integer,
    source_id uuid,
    source_url text,
    retrieved_at timestamp with time zone,
    is_pains_positive boolean default false not null,
    constraint compounds_pkey primary key (compound_id),
    constraint compounds_canonical_key_key unique (canonical_key),
    constraint compounds_num_ro5_violations_check check (num_ro5_violations is null or (num_ro5_violations >= 0 and num_ro5_violations <= 4))
);

create table public.targets (
    target_id uuid not null,
    canonical_key text not null,
    gene_symbol text,
    protein_name text,
    uniprot_accession text,
    source_id uuid,
    source_url text,
    retrieved_at timestamp with time zone,
    constraint targets_pkey primary key (target_id),
    constraint targets_canonical_key_key unique (canonical_key)
);

create table public.diseases (
    disease_id uuid not null,
    canonical_key text not null,
    disease_name text,
    ontology_id text,
    ontology_source text,
    source_id uuid,
    source_url text,
    retrieved_at timestamp with time zone,
    constraint diseases_pkey primary key (disease_id),
    constraint diseases_canonical_key_key unique (canonical_key)
);
