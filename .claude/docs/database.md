# Database Schema

PostgreSQL. All tables use snake_case. All timestamps are `timestamptz`.

---

## Naming conventions

| Pattern           | Meaning                                                            |
| ----------------- | ------------------------------------------------------------------ |
| `*_id`            | Stable primary key                                                 |
| `*_key`           | Deduplication / lookup key (usually slugified)                     |
| `canonical_*`     | Final accepted entity name                                         |
| `*_aliases`       | All non-canonical names for an entity                              |
| `source_name`     | External system name (e.g. `KNApSAcK World`), never an entity name |
| `retrieved_at`    | When the record was fetched from the source                        |
| `source_batch_id` | Which ETL run produced it                                          |
| `confidence`      | Numeric match quality (0–1 float)                                  |
---

## 1. Provenance

### `source_systems`

One row per external data source.

| Column        | Type | Notes                                                                     |
| ------------- | ---- | ------------------------------------------------------------------------- |
| `source_id`   | PK   |                                                                           |
| `source_name` | text | e.g. `KNApSAcK World`, `GBIF`, `PubChem`, `UniProt`, `STRING`, `DisGeNET` |
| `source_type` | enum | `scrape` / `api` / `download` / `manual`                                  |
| `base_url`    | text |                                                                           |
| `notes`       | text |                                                                           |

### `import_batches`

One row per ETL run.

| Column        | Type        | Notes |
| ------------- | ----------- | ----- |
| `batch_id`    | PK          |       |
| `step_name`   | text        |       |
| `started_at`  | timestamptz |       |

---

## 2. Plants

### `plants`

One canonical row per accepted plant taxon.

| Column                      | Type                  | Notes                                     |
| --------------------------- | --------------------- | ----------------------------------------- |
| `plant_id`                  | PK                    |                                           |
| `canonical_key`             | text                  | unique                                    |
| `canonical_scientific_name` | text                  | cleaned accepted name only, no authorship |
| `authorship`                | text                  | separate from name                        |
| `family_name`               | text                  |                                           |
| `taxonomic_status`          | text                  |                                           |
| `rank`                      | text                  |                                           |
| `gbif_usage_key`            | int                   |                                           |
| `gbif_accepted_usage_key`   | int                   |                                           |
| `gbif_species_key`          | int                   |                                           |
| `gbif_genus_key`            | int                   |                                           |
| `gbif_family_key`           | int                   |                                           |
| `gbif_kingdom_key`          | int                   |                                           |
| `source_id`                 | FK → `source_systems` | the system, not a plant name              |
| `source_url`                | text                  |                                           |
| `source_batch_id`           | FK → `import_batches` |                                           |
| `retrieved_at`              | timestamptz           |                                           |
| `confidence`                | float                 |                                           |

### `plant_aliases`

All alternate names for a canonical plant. Each alias belongs to exactly one plant (no m:m needed here).

| Column            | Type                  | Notes                                                                                             |
| ----------------- | --------------------- | ------------------------------------------------------------------------------------------------- |
| `alias_id`        | PK                    |                                                                                                   |
| `plant_id`        | FK → `plants`         |                                                                                                   |
| `alias_name`      | text                  |                                                                                                   |
| `alias_key`       | text                  |                                                                                                   |
| `alias_type`      | enum                  | `scraped_spelling` / `synonym` / `author_variant` / `orthographic_variant` / `normalized_variant` |
| `source_id`       | FK → `source_systems` |                                                                                                   |
| `source_url`      | text                  |                                                                                                   |
| `source_batch_id` | FK → `import_batches` |                                                                                                   |
| `retrieved_at`    | timestamptz           |                                                                                                   |

---

## 3. Compounds

### `compounds`

One canonical row per chemical entity.

| Column              | Type                  | Notes  |
| ------------------- | --------------------- | ------ |
| `compound_id`       | PK                    |        |
| `canonical_key`     | text                  | unique |
| `canonical_name`    | text                  |        |
| `inchi_key`         | text                  |        |
| `smiles`            | text                  |        |
| `cas_id`            | text                  |        |
| `pubchem_cid`       | text                  |        |
| `chembl_id`         | text                  |        |
| `molecular_formula` | text                  |        |
| `molecular_weight`  | float                 |        |
| `tpsa`              | float                 |        |
| `logp`              | float                 |        |
| `hbond_donors`      | int                   |        |
| `hbond_acceptors`   | int                   |        |
| `source_id`         | FK → `source_systems` |        |
| `source_url`        | text                  |        |
| `source_batch_id`   | FK → `import_batches` |        |
| `retrieved_at`      | timestamptz           |        |
| `confidence`        | float                 |        |

### `compound_aliases`

| Column              | Type                  | Notes |
| ------------------- | --------------------- | ----- |
| `compound_alias_id` | PK                    |       |
| `compound_id`       | FK → `compounds`      |       |
| `alias_name`        | text                  |       |
| `alias_key`         | text                  |       |
| `alias_type`        | text                  |       |
| `source_id`         | FK → `source_systems` |       |
| `source_url`        | text                  |       |
| `source_batch_id`   | FK → `import_batches` |       |
| `retrieved_at`      | timestamptz           |       |

### `plant_compounds`

m:m join. Answers: which compounds were found in which plants?

| Column                   | Type                               | Notes                 |
| ------------------------ | ---------------------------------- | --------------------- |
| `plant_compound_id`      | PK                                 |                       |
| `plant_id`               | FK → `plants`                      |                       |
| `compound_id`            | FK → `compounds`                   |                       |
| `source_plant_raw_id`    | text                               | optional traceability |
| `source_compound_raw_id` | text                               | optional              |
| `source_id`              | FK → `source_systems`              |                       |
| `evidence_type`          | text                               |                       |
| `confidence`             | float                              |                       |
| `retrieved_at`           | timestamptz                        |                       |

Unique constraint: `(plant_id, compound_id, source_id)`

---

## 4. Targets

### `targets`

Canonical protein/gene entities.

| Column              | Type                  | Notes  |
| ------------------- | --------------------- | ------ |
| `target_id`         | PK                    |        |
| `canonical_key`     | text                  | unique |
| `gene_symbol`       | text                  |        |
| `protein_name`      | text                  |        |
| `uniprot_accession` | text                  |        |
| `organism_tax_id`   | int                   |        |
| `source_id`         | FK → `source_systems` |        |
| `source_url`        | text                  |        |
| `source_batch_id`   | FK → `import_batches` |        |
| `retrieved_at`      | timestamptz           |        |
| `confidence`        | float                 |        |

### `target_aliases`

| Column            | Type                  | Notes |
| ----------------- | --------------------- | ----- |
| `target_alias_id` | PK                    |       |
| `target_id`       | FK → `targets`        |       |
| `alias_name`      | text                  |       |
| `alias_key`       | text                  |       |
| `alias_type`      | text                  |       |
| `source_id`       | FK → `source_systems` |       |
| `source_url`      | text                  |       |
| `source_batch_id` | FK → `import_batches` |       |
| `retrieved_at`    | timestamptz           |       |

### `compound_targets`

m:m join. Answers: which targets are linked to which compounds?

| Column               | Type                  | Notes |
| -------------------- | --------------------- | ----- |
| `compound_target_id` | PK                    |       |
| `compound_id`        | FK → `compounds`      |       |
| `target_id`          | FK → `targets`        |       |
| `source_id`          | FK → `source_systems` |       |
| `prediction_method`  | text                  |       |
| `evidence_type`      | text                  |       |
| `score`              | float                 |       |
| `confidence`         | float                 |       |
| `retrieved_at`       | timestamptz           |       |

Unique constraint: `(compound_id, target_id, source_id)`

---

## 5. Diseases

### `diseases`

| Column            | Type                  | Notes                                   |
| ----------------- | --------------------- | --------------------------------------- |
| `disease_id`      | PK                    |                                         |
| `canonical_key`   | text                  | unique                                  |
| `disease_name`    | text                  |                                         |
| `ontology_id`     | text                  | MeSH / DOID / UMLS / OMIM / DisGeNET ID |
| `ontology_source` | text                  |                                         |
| `source_id`       | FK → `source_systems` |                                         |
| `source_url`      | text                  |                                         |
| `source_batch_id` | FK → `import_batches` |                                         |
| `retrieved_at`    | timestamptz           |                                         |
| `confidence`      | float                 |                                         |

### `disease_aliases`

| Column             | Type                  | Notes |
| ------------------ | --------------------- | ----- |
| `disease_alias_id` | PK                    |       |
| `disease_id`       | FK → `diseases`       |       |
| `alias_name`       | text                  |       |
| `alias_key`        | text                  |       |
| `alias_type`       | text                  |       |
| `source_id`        | FK → `source_systems` |       |
| `source_url`       | text                  |       |
| `source_batch_id`  | FK → `import_batches` |       |
| `retrieved_at`     | timestamptz           |       |

### `disease_targets`

m:m join. Answers: which targets are implicated in which diseases?

| Column              | Type                  | Notes |
| ------------------- | --------------------- | ----- |
| `disease_target_id` | PK                    |       |
| `disease_id`        | FK → `diseases`       |       |
| `target_id`         | FK → `targets`        |       |
| `source_id`         | FK → `source_systems` |       |
| `association_type`  | text                  |       |
| `score`             | float                 |       |
| `confidence`        | float                 |       |
| `retrieved_at`      | timestamptz           |       |

Unique constraint: `(disease_id, target_id, source_id)`

---

## 6. PPI / network

### `ppi_edges`

Protein-protein interaction edges. Nodes are in `targets` — no separate `ppi_nodes` table.

| Column               | Type                    | Notes                                                         |
| -------------------- | ----------------------- | ------------------------------------------------------------- |
| `ppi_edge_id`        | PK                      |                                                               |
| `target_a_id`        | FK → `targets`          | always `target_a_id < target_b_id` to prevent duplicate pairs |
| `target_b_id`        | FK → `targets`          |                                                               |
| `source_id`          | FK → `source_systems`   |                                                               |
| `combined_score`     | float                   |                                                               |
| `experimental_score` | float                   |                                                               |
| `database_score`     | float                   |                                                               |
| `textmining_score`   | float                   |                                                               |
| `coexpression_score` | float                   |                                                               |
| `neighborhood_score` | float                   |                                                               |
| `fusion_score`       | float                   |                                                               |
| `cooccurrence_score` | float                   |                                                               |
| `retrieved_at`       | timestamptz             |                                                               |

Unique constraint: `(target_a_id, target_b_id, source_id)`

> Always insert pairs in sorted order so A–B and B–A are never stored as separate rows.

---

## 7. Analysis runs

### `analysis_runs`

| Column          | Type            | Notes    |
| --------------- | --------------- | -------- |
| `analysis_id`   | PK              |          |
| `analysis_name` | text            |          |
| `disease_id`    | FK → `diseases` | optional |
| `notes`         | text            |          |
| `parameters`    | jsonb           |          |
| `status`        | text            |          |
| `created_at`    | timestamptz     |          |
| `created_by`    | text            |          |

### `analysis_run_plants`

Unique: `(analysis_id, plant_id)`

### `analysis_run_compounds`

Unique: `(analysis_id, compound_id)`

### `analysis_run_targets`

Unique: `(analysis_id, target_id)`

### `analysis_run_diseases`

Unique: `(analysis_id, disease_id)`

### `analysis_run_ppi_edges`

Snapshot of network edges used in a run. Optional.
Unique: `(analysis_id, ppi_edge_id)`

---

## 8. Derived outputs

### `target_rankings`

| Column                      | Type                 | Notes |
| --------------------------- | -------------------- | ----- |
| `ranking_id`                | PK                   |       |
| `analysis_id`               | FK → `analysis_runs` |       |
| `target_id`                 | FK → `targets`       |       |
| `degree_centrality`         | float                |       |
| `betweenness_centrality`    | float                |       |
| `closeness_centrality`      | float                |       |
| `eigenvector_centrality`    | float                |       |
| `disease_association_score` | float                |       |
| `compound_support_score`    | float                |       |
| `final_score`               | float                |       |
| `rank_position`             | int                  |       |
| `created_at`                | timestamptz          |       |

Unique: `(analysis_id, target_id)`

### `pathways`

| Column         | Type | Notes |
| -------------- | ---- | ----- |
| `pathway_id`   | PK   |       |
| `pathway_code` | text |       |
| `pathway_name` | text |       |
| `source_name`  | text |       |
| `source_url`   | text |       |

### `target_pathways`

m:m join between targets and pathways.

| Column              | Type                  | Notes |
| ------------------- | --------------------- | ----- |
| `target_pathway_id` | PK                    |       |
| `target_id`         | FK → `targets`        |       |
| `pathway_id`        | FK → `pathways`       |       |
| `source_id`         | FK → `source_systems` |       |
| `p_value`           | float                 |       |
| `fdr`               | float                 |       |
| `confidence`        | float                 |       |

Unique: `(target_id, pathway_id, source_id)`

---

## What is not a table

These relations are query-derived, not stored:

- plant → disease (go through compounds → targets → diseases)
- compound → disease (go through targets → diseases)
- plant → target (go through compounds → targets)

The pipeline is: `plants → compounds → targets → diseases → PPI`

---

## Build order

```
Phase 1 (plants)
  source_systems, import_batches
  plants, plant_aliases

Phase 2 (compounds)
  compounds, compound_aliases
  plant_compounds

Phase 3 (targets)
  targets, target_aliases
  compound_targets

Phase 4 (diseases)
  diseases, disease_aliases
  disease_targets

Phase 5 (network + analysis)
  ppi_edges
  analysis_runs, analysis_run_*
  target_rankings, pathways, target_pathways
```
