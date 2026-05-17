-- ============================================================
-- 1. PROVENANCE
-- ============================================================

create table source_systems (
  source_id     uuid primary key default gen_random_uuid(),
  source_name   text not null unique,
  source_type   text not null check (source_type in ('scrape','api','download','manual')),
  base_url      text,
  notes         text
);

create table source_snapshots (
  source_snapshot_id uuid primary key default gen_random_uuid(),
  source_id          uuid not null references source_systems(source_id),
  version_label      text,
  source_url         text,
  retrieved_at       timestamptz,
  checksum           text,
  metadata           jsonb
);

create table import_batches (
  batch_id             uuid primary key default gen_random_uuid(),
  step_name            text,
  source_snapshot_id   uuid references source_snapshots(source_snapshot_id),
  status               text,
  started_at           timestamptz,
  finished_at          timestamptz,
  params               jsonb,
  log_path             text
);

create table api_cache (
  cache_id       uuid primary key default gen_random_uuid(),
  provider       text,
  cache_key      text unique,
  request_json   jsonb,
  response_json  jsonb,
  response_hash  text,
  fetched_at     timestamptz,
  expires_at     timestamptz
);

create table validation_reports (
  report_id   uuid primary key default gen_random_uuid(),
  batch_id    uuid references import_batches(batch_id),
  report_type text,
  report_path text,
  summary     jsonb,
  created_at  timestamptz
);

-- ============================================================
-- 2. STAGING
-- ============================================================

create table stg_plants (
  raw_id          uuid primary key default gen_random_uuid(),
  source_batch_id text,
  plant_id        text,
  species_name    text,
  family_name     text,
  common_name     text,
  classification  text,
  purpose         text,
  reference       text,
  detail_url      text,
  raw_row         jsonb,
  raw_hash        text,
  imported_at     timestamptz
);

create table stg_plant_compounds (
  raw_id             uuid primary key default gen_random_uuid(),
  source_batch_id    text,
  plant_id           text,
  c_id               text,
  cas_id             text,
  metabolite         text,
  molecular_formula  text,
  mw                 float,
  organism           text,
  raw_row            jsonb,
  raw_hash           text,
  imported_at        timestamptz
);

-- ============================================================
-- 3. PLANTS
-- ============================================================

create table plants (
  plant_id                    text primary key,
  canonical_key               text not null unique,
  canonical_scientific_name   text,
  authorship                  text,
  family_name                 text,
  taxonomic_status            text,
  rank                        text,
  gbif_usage_key              int,
  gbif_accepted_usage_key     int,
  gbif_species_key            int,
  gbif_genus_key              int,
  gbif_family_key             int,
  gbif_kingdom_key            int,
  source_id                   uuid references source_systems(source_id),
  source_url                  text,
  source_batch_id             uuid references import_batches(batch_id),
  retrieved_at                timestamptz,
  confidence                  float
);

create table plant_aliases (
  alias_id        text primary key,
  plant_id        text not null references plants(plant_id),
  alias_name      text,
  alias_key       text,
  alias_type      text,
  source_id       uuid references source_systems(source_id),
  source_url      text,
  source_batch_id uuid references import_batches(batch_id),
  retrieved_at    timestamptz
);

-- ============================================================
-- 4. COMPOUNDS
-- ============================================================

create table compounds (
  compound_id         text primary key,
  canonical_key       text not null unique,
  canonical_name      text,
  inchi_key           text,
  smiles              text,
  cas_id              text,
  pubchem_cid         text,
  chembl_id           text,
  molecular_formula   text,
  molecular_weight    float,
  tpsa                float,
  logp                float,
  hbond_donors        int,
  hbond_acceptors     int,
  rotatable_bonds     int,
  qed_score           float,
  np_likeness_score   float,
  num_ro5_violations  int,
  source_id           uuid references source_systems(source_id),
  source_url          text,
  source_batch_id     uuid references import_batches(batch_id),
  retrieved_at        timestamptz,
  confidence          float
);

create table compound_aliases (
  compound_alias_id  text primary key,
  compound_id        text not null references compounds(compound_id),
  alias_name         text,
  alias_key          text,
  alias_type         text,
  source_id          uuid references source_systems(source_id),
  source_url         text,
  source_batch_id    uuid references import_batches(batch_id),
  retrieved_at       timestamptz
);

create table plant_compounds (
  plant_compound_id       text primary key,
  plant_id                text not null references plants(plant_id),
  compound_id             text not null references compounds(compound_id),
  source_plant_raw_id     text,
  source_compound_raw_id  text,
  source_id               uuid references source_systems(source_id),
  evidence_type           text,
  confidence              float,
  retrieved_at            timestamptz,
  unique (plant_id, compound_id, source_id)
);

-- ============================================================
-- 5. TARGETS
-- ============================================================

create table targets (
  target_id           text primary key,
  canonical_key       text not null unique,
  gene_symbol         text,
  protein_name        text,
  uniprot_accession   text,
  organism_tax_id     int,
  source_id           uuid references source_systems(source_id),
  source_url          text,
  source_batch_id     uuid references import_batches(batch_id),
  retrieved_at        timestamptz,
  confidence          float
);

create table target_aliases (
  target_alias_id text primary key,
  target_id       text not null references targets(target_id),
  alias_name      text,
  alias_key       text,
  alias_type      text,
  source_id       uuid references source_systems(source_id),
  source_url      text,
  source_batch_id uuid references import_batches(batch_id),
  retrieved_at    timestamptz
);

create table compound_targets (
  compound_target_id  text primary key,
  compound_id         text not null references compounds(compound_id),
  target_id           text not null references targets(target_id),
  source_id           uuid references source_systems(source_id),
  prediction_method   text,
  evidence_type       text,
  score               float,
  confidence          float,
  retrieved_at        timestamptz,
  unique (compound_id, target_id, source_id)
);

-- ============================================================
-- 6. DISEASES
-- ============================================================

create table diseases (
  disease_id      text primary key,
  canonical_key   text not null unique,
  disease_name    text,
  ontology_id     text,
  ontology_source text,
  source_id       uuid references source_systems(source_id),
  source_url      text,
  source_batch_id uuid references import_batches(batch_id),
  retrieved_at    timestamptz,
  confidence      float
);

create table disease_aliases (
  disease_alias_id  text primary key,
  disease_id        text not null references diseases(disease_id),
  alias_name        text,
  alias_key         text,
  alias_type        text,
  source_id         uuid references source_systems(source_id),
  source_url        text,
  source_batch_id   uuid references import_batches(batch_id),
  retrieved_at      timestamptz
);

create table disease_targets (
  disease_target_id  text primary key,
  disease_id         text not null references diseases(disease_id),
  target_id          text not null references targets(target_id),
  source_id          uuid references source_systems(source_id),
  association_type   text,
  score              float,
  confidence         float,
  retrieved_at       timestamptz,
  unique (disease_id, target_id, source_id)
);

-- ============================================================
-- 7. PPI / NETWORK
-- ============================================================

create table ppi_edges (
  ppi_edge_id          uuid primary key default gen_random_uuid(),
  target_a_id          text not null references targets(target_id),
  target_b_id          text not null references targets(target_id),
  source_id            uuid references source_systems(source_id),
  source_snapshot_id   uuid references source_snapshots(source_snapshot_id),
  combined_score       float,
  experimental_score   float,
  database_score       float,
  textmining_score     float,
  coexpression_score   float,
  neighborhood_score   float,
  fusion_score         float,
  cooccurrence_score   float,
  retrieved_at         timestamptz,
  unique (target_a_id, target_b_id, source_id),
  check (target_a_id < target_b_id)
);

-- ============================================================
-- 8. ANALYSIS RUNS
-- ============================================================

create table analysis_runs (
  analysis_id    uuid primary key default gen_random_uuid(),
  analysis_name  text,
  disease_id     text references diseases(disease_id),
  notes          text,
  parameters     jsonb,
  status         text,
  created_at     timestamptz,
  created_by     text
);

create table analysis_run_plants (
  analysis_id  uuid not null references analysis_runs(analysis_id),
  plant_id     text not null references plants(plant_id),
  unique (analysis_id, plant_id)
);

create table analysis_run_compounds (
  analysis_id  uuid not null references analysis_runs(analysis_id),
  compound_id  text not null references compounds(compound_id),
  unique (analysis_id, compound_id)
);

create table analysis_run_targets (
  analysis_id  uuid not null references analysis_runs(analysis_id),
  target_id    text not null references targets(target_id),
  unique (analysis_id, target_id)
);

create table analysis_run_diseases (
  analysis_id  uuid not null references analysis_runs(analysis_id),
  disease_id   text not null references diseases(disease_id),
  unique (analysis_id, disease_id)
);

create table analysis_run_ppi_edges (
  analysis_id  uuid not null references analysis_runs(analysis_id),
  ppi_edge_id  uuid not null references ppi_edges(ppi_edge_id),
  unique (analysis_id, ppi_edge_id)
);

-- ============================================================
-- 9. DERIVED OUTPUTS
-- ============================================================

create table target_rankings (
  ranking_id                   uuid primary key default gen_random_uuid(),
  analysis_id                  uuid not null references analysis_runs(analysis_id),
  target_id                    text not null references targets(target_id),
  degree_centrality            float,
  betweenness_centrality       float,
  closeness_centrality         float,
  eigenvector_centrality       float,
  disease_association_score    float,
  compound_support_score       float,
  final_score                  float,
  rank_position                int,
  created_at                   timestamptz,
  unique (analysis_id, target_id)
);

create table pathways (
  pathway_id    uuid primary key default gen_random_uuid(),
  pathway_code  text,
  pathway_name  text,
  source_name   text,
  source_url    text
);

create table target_pathways (
  target_pathway_id  uuid primary key default gen_random_uuid(),
  target_id          text not null references targets(target_id),
  pathway_id         uuid not null references pathways(pathway_id),
  source_id          uuid references source_systems(source_id),
  p_value            float,
  fdr                float,
  confidence         float,
  unique (target_id, pathway_id, source_id)
);
