-- Baseline (3/7): alias tables.
--
-- One alias table per entity. Each holds alternate names keyed by a normalized
-- alias_key, unique per (parent, alias_key). Foreign keys to the parent entity
-- are added in 0006.

create table public.plant_aliases (
    alias_id uuid not null,
    plant_id uuid not null,
    alias_name text,
    alias_key text,
    alias_type text,
    retrieved_at timestamp with time zone,
    constraint plant_aliases_pkey primary key (alias_id),
    constraint plant_aliases_parent_key unique (plant_id, alias_key)
);

create table public.compound_aliases (
    compound_alias_id uuid not null,
    compound_id uuid not null,
    alias_name text,
    alias_key text,
    alias_type text,
    retrieved_at timestamp with time zone,
    constraint compound_aliases_pkey primary key (compound_alias_id),
    constraint compound_aliases_parent_key unique (compound_id, alias_key)
);

create table public.target_aliases (
    target_alias_id uuid not null,
    target_id uuid not null,
    alias_name text,
    alias_key text,
    alias_type text,
    retrieved_at timestamp with time zone,
    constraint target_aliases_pkey primary key (target_alias_id),
    constraint target_aliases_parent_key unique (target_id, alias_key)
);

create table public.disease_aliases (
    disease_alias_id uuid not null,
    disease_id uuid not null,
    alias_name text,
    alias_key text,
    alias_type text,
    retrieved_at timestamp with time zone,
    constraint disease_aliases_pkey primary key (disease_alias_id),
    constraint disease_aliases_parent_key unique (disease_id, alias_key)
);
