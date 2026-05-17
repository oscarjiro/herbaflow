create index on plants(canonical_key);
create index on plants(source_id);
create index on plants(gbif_usage_key);
create index on plant_aliases(plant_id);
create index on plant_aliases(alias_key);

create index on compounds(canonical_key);
create index on compounds(inchi_key);
create index on compounds(pubchem_cid);
create index on compounds(chembl_id);
create index on compounds(source_id);
create index on compound_aliases(compound_id);
create index on compound_aliases(alias_key);
create index on plant_compounds(plant_id);
create index on plant_compounds(compound_id);

create index on targets(canonical_key);
create index on targets(uniprot_accession);
create index on targets(gene_symbol);
create index on target_aliases(target_id);
create index on target_aliases(alias_key);
create index on compound_targets(compound_id);
create index on compound_targets(target_id);

create index on diseases(canonical_key);
create index on diseases(ontology_id);
create index on disease_aliases(disease_id);
create index on disease_targets(disease_id);
create index on disease_targets(target_id);

create index on ppi_edges(target_a_id);
create index on ppi_edges(target_b_id);
