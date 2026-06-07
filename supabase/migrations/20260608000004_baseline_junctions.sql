-- Baseline (4/7): junction tables.
--
-- Pair-grain relationship tables, each unique per entity pair. Foreign keys to
-- the entities and to source_systems are added in 0006.

create table public.plant_compounds (
    plant_compound_id uuid not null,
    plant_id uuid not null,
    compound_id uuid not null,
    source_id uuid,
    retrieved_at timestamp with time zone,
    source_url text,
    constraint plant_compounds_pkey primary key (plant_compound_id),
    constraint plant_compounds_pair_key unique (plant_id, compound_id)
);

create table public.compound_targets (
    compound_target_id uuid not null,
    compound_id uuid not null,
    target_id uuid not null,
    source_id uuid,
    prediction_method text,
    score double precision,
    retrieved_at timestamp with time zone,
    pchembl_value double precision,
    source_url text,
    constraint compound_targets_pkey primary key (compound_target_id),
    constraint compound_targets_pair_key unique (compound_id, target_id),
    constraint compound_targets_prediction_method_check check (prediction_method is null or prediction_method in ('chembl_bioactivity', 'pubchem_bioassay', 'stp_import'))
);

create table public.disease_targets (
    disease_target_id uuid not null,
    disease_id uuid not null,
    target_id uuid not null,
    source_id uuid,
    association_type text,
    score double precision,
    retrieved_at timestamp with time zone,
    source_url text,
    constraint disease_targets_pkey primary key (disease_target_id),
    constraint disease_targets_pair_key unique (disease_id, target_id)
);
