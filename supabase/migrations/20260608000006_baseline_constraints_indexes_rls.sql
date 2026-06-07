-- Baseline (6/7): foreign keys, indexes, row-level security.
--
-- Added after every table exists so replay is order-independent. Row-level
-- security is enabled on all 13 tables (no policies defined; access is via the
-- service role with the public Data API disabled).

-- Foreign keys: entities -> source_systems.
alter table only public.plants
    add constraint plants_source_id_fkey foreign key (source_id) references public.source_systems(source_id);
alter table only public.compounds
    add constraint compounds_source_id_fkey foreign key (source_id) references public.source_systems(source_id);
alter table only public.targets
    add constraint targets_source_id_fkey foreign key (source_id) references public.source_systems(source_id);
alter table only public.diseases
    add constraint diseases_source_id_fkey foreign key (source_id) references public.source_systems(source_id);

-- Foreign keys: aliases -> parent entity.
alter table only public.plant_aliases
    add constraint plant_aliases_plant_id_fkey foreign key (plant_id) references public.plants(plant_id);
alter table only public.compound_aliases
    add constraint compound_aliases_compound_id_fkey foreign key (compound_id) references public.compounds(compound_id);
alter table only public.target_aliases
    add constraint target_aliases_target_id_fkey foreign key (target_id) references public.targets(target_id);
alter table only public.disease_aliases
    add constraint disease_aliases_disease_id_fkey foreign key (disease_id) references public.diseases(disease_id);

-- Foreign keys: junctions -> entities + source_systems.
alter table only public.plant_compounds
    add constraint plant_compounds_plant_id_fkey foreign key (plant_id) references public.plants(plant_id);
alter table only public.plant_compounds
    add constraint plant_compounds_compound_id_fkey foreign key (compound_id) references public.compounds(compound_id);
alter table only public.plant_compounds
    add constraint plant_compounds_source_id_fkey foreign key (source_id) references public.source_systems(source_id);
alter table only public.compound_targets
    add constraint compound_targets_compound_id_fkey foreign key (compound_id) references public.compounds(compound_id);
alter table only public.compound_targets
    add constraint compound_targets_target_id_fkey foreign key (target_id) references public.targets(target_id);
alter table only public.compound_targets
    add constraint compound_targets_source_id_fkey foreign key (source_id) references public.source_systems(source_id);
alter table only public.disease_targets
    add constraint disease_targets_disease_id_fkey foreign key (disease_id) references public.diseases(disease_id);
alter table only public.disease_targets
    add constraint disease_targets_target_id_fkey foreign key (target_id) references public.targets(target_id);
alter table only public.disease_targets
    add constraint disease_targets_source_id_fkey foreign key (source_id) references public.source_systems(source_id);

-- Foreign key: analysis_runs -> diseases.
alter table only public.analysis_runs
    add constraint analysis_runs_disease_id_fkey foreign key (disease_id) references public.diseases(disease_id);

-- Indexes.
create index compound_aliases_alias_key_idx on public.compound_aliases using btree (alias_key);
create index compound_aliases_compound_id_idx on public.compound_aliases using btree (compound_id);
create index compound_targets_compound_id_idx on public.compound_targets using btree (compound_id);
create index compound_targets_target_id_idx on public.compound_targets using btree (target_id);
create index compounds_chembl_id_idx on public.compounds using btree (chembl_id);
create index compounds_inchi_key_idx on public.compounds using btree (inchi_key);
create index compounds_pubchem_cid_idx on public.compounds using btree (pubchem_cid);
create index compounds_source_id_idx on public.compounds using btree (source_id);
create index disease_aliases_disease_id_idx on public.disease_aliases using btree (disease_id);
create index disease_targets_disease_id_idx on public.disease_targets using btree (disease_id);
create index disease_targets_target_id_idx on public.disease_targets using btree (target_id);
create index diseases_ontology_id_idx on public.diseases using btree (ontology_id);
create index idx_analysis_runs_expires_at on public.analysis_runs using btree (expires_at);
create index idx_analysis_runs_status on public.analysis_runs using btree (status);
create index idx_disease_aliases_alias_key on public.disease_aliases using btree (alias_key);
create index idx_disease_targets_score on public.disease_targets using btree (score);
create index idx_targets_gene_symbol on public.targets using btree (gene_symbol);
create index idx_targets_uniprot_accession on public.targets using btree (uniprot_accession);
create index plant_aliases_alias_key_idx on public.plant_aliases using btree (alias_key);
create index plant_aliases_plant_id_idx on public.plant_aliases using btree (plant_id);
create index plant_compounds_compound_id_idx on public.plant_compounds using btree (compound_id);
create index plant_compounds_plant_id_idx on public.plant_compounds using btree (plant_id);
create index plants_source_id_idx on public.plants using btree (source_id);
create index target_aliases_alias_key_idx on public.target_aliases using btree (alias_key);
create index target_aliases_target_id_idx on public.target_aliases using btree (target_id);

-- Row-level security (enabled on all tables; no policies).
alter table public.plants enable row level security;
alter table public.compounds enable row level security;
alter table public.targets enable row level security;
alter table public.diseases enable row level security;
alter table public.plant_aliases enable row level security;
alter table public.compound_aliases enable row level security;
alter table public.target_aliases enable row level security;
alter table public.disease_aliases enable row level security;
alter table public.plant_compounds enable row level security;
alter table public.compound_targets enable row level security;
alter table public.disease_targets enable row level security;
alter table public.source_systems enable row level security;
alter table public.analysis_runs enable row level security;
