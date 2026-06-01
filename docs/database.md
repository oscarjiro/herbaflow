# Database Schema

PostgreSQL. All tables use snake_case. All timestamps are `timestamptz`.

---

## Primary key format

All primary keys are **bare UUID v5 strings** derived as `uuid5(NAMESPACE, canonical_key)`. No entity type prefixes (`pl_`, `tgt_`, etc.) are used — the column name (`plant_id`, `target_id`) provides type context in the schema.

Every namespace, canonical-key cascade, and id/alias/bridge builder lives in one place — `etl/shared/identity.py` — which each module's `utils.py` re-exports. The backend mirrors the three ids it mints (`compound_id`, `target_id`, `compound_target_id`) in `backend/app/services/canonicalize.py`, kept byte-identical by parity tests. `canonical_key` is single-colon `{source}:{id}` (CURIE-style).

| Entity | Namespace `uuid5(NAMESPACE_DNS, …)` | canonical_key (the uuid5 input) |
|---|---|---|
| `plant_id` | `"herbaflow.plants"` | `gbif:{usageKey}` → `plant:{slug}` fallback |
| `compound_id` | `"herbaflow.compounds"` | cascade: `inchikey:` > `pubchem:` > `chembl:` > `cas:` > `name_formula:` > `name:` > `formula:` |
| `target_id` | `"herbaflow.targets"` | `uniprot:{acc}` (isoform-folded) → `ensembl:{id}` → `gene:{SYMBOL}` |
| `disease_id` | `"herbaflow.diseases"` | `doid:{id}` / `mesh:{id}` → `disease:{slug}` fallback |
| `plant_compound_id` | `"herbaflow.plant_compounds"` | `{plant_id}:{compound_id}` (pair grain) |
| `compound_target_id` | `"herbaflow.compound_targets"` | `{compound_id}:{target_id}` (pair grain) |
| `disease_target_id` | `"herbaflow.disease_targets"` | `{disease_id}:{target_id}` (pair grain) |

Bridge ids key on `{left_id}:{right_id}` — `source_id` is **not** part of identity (bridges are one row per entity pair). Alias ids key on `{parent_id}:{alias_key}` — `alias_type` is **not** part of identity (one row per parent+slug). `canonical_key` is also stored as a `UNIQUE` alternate key on each entity table: a deliberate derived-key denormalization for fast lookup.

IDs are deterministic: same input always produces the same UUID. At the bundled reload every entity, alias, and bridge id is re-derived from these keys — all change except where the key is unchanged (most `target_id`s stay; isoform-bearing accessions fold and change).

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
---

## 1. Provenance

### `source_systems`

One row per external data source.

| Column        | Type | Notes                                                                     |
| ------------- | ---- | ------------------------------------------------------------------------- |
| `source_id`   | PK   |                                                                           |
| `source_name` | text | e.g. `KNApSAcK World`, `GBIF`, `PubChem`, `UniProt`, `STRING` |
| `source_type` | enum | `scrape` / `api` / `download` / `manual`                                  |
| `base_url`    | text |                                                                           |
| `notes`       | text |                                                                           |

### `import_batches`

One row per ETL run.

| Column        | Type        | Notes |
| ------------- | ----------- | ----- |
| `batch_id`    | PK          |       |
| `step_name`   | text        |       |
| `status`      | text        |       |
| `started_at`  | timestamptz |       |
| `finished_at` | timestamptz |       |
| `params`      | jsonb       | pipeline parameters passed to this run |
| `log_path`    | text        | filesystem path to the ETL log file |

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

Unique constraint: `(plant_id, alias_key)` — one row per plant + slug; `alias_type` is an attribute. Index: `plant_aliases(alias_key)`.

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
| `rotatable_bonds`   | int                   |        |
| `num_ro5_violations` | int                  | count of Lipinski Rule of Five violations (0–4); 0 = fully drug-like |
| `qed_score`         | float                 | Quantitative Estimate of Drug-likeness (0–1, higher = more drug-like); computed by RDKit |
| `np_likeness_score` | float                 | Natural product-likeness score (RDKit); ≥ 0.5 triggers NP exception in ADME filtering |
| `is_pains_positive` | boolean NOT NULL DEFAULT false | PAINS flag (Baell & Holloway 2010); true = matches pan-assay interference pattern. Reporting only — not a filter. Populated by ETL `patch_missing_lipinski.py` Pass 3. |
| `lipinski_source`   | text                  | `chembl_api` = from ChEMBL molecule_properties; `rdkit_computed` = computed from SMILES; null = unresolved |
| `source_id`         | FK → `source_systems` |        |
| `source_url`        | text                  |        |
| `source_batch_id`   | FK → `import_batches` |        |
| `retrieved_at`      | timestamptz           |        |

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

Unique constraint: `(compound_id, alias_key)` — one row per compound + slug; `alias_type` is an attribute. Index: `compound_aliases(alias_key)`.

### `plant_compounds`

m:m join. Answers: which compounds were found in which plants?

| Column                   | Type                               | Notes                 |
| ------------------------ | ---------------------------------- | --------------------- |
| `plant_compound_id`      | PK                                 |                       |
| `plant_id`               | FK → `plants`                      |                       |
| `compound_id`            | FK → `compounds`                   |                       |
| `source_id`              | FK → `source_systems`              |                       |
| `retrieved_at`           | timestamptz                        |                       |

Unique constraint: `(plant_id, compound_id)` — pair grain; `source_id` is an attribute, not part of the key.

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

Indexes: `idx_targets_uniprot_accession` on `uniprot_accession`; `idx_targets_gene_symbol` on `gene_symbol`.

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

Unique constraint: `(target_id, alias_key)` — one row per target + slug; `alias_type` is an attribute. Index: `target_aliases(alias_key)`.

### `compound_targets`

m:m join. Answers: which targets are linked to which compounds?

| Column               | Type                  | Notes |
| -------------------- | --------------------- | ----- |
| `compound_target_id` | PK                    |       |
| `compound_id`        | FK → `compounds`      |       |
| `target_id`          | FK → `targets`        |       |
| `source_id`          | FK → `source_systems` |       |
| `prediction_method`  | text                  | sole compound-target link provenance (chembl_bioactivity / pubchem_bioassay / stp_import) |
| `score`              | float                 |       |
| `pchembl_value`      | float                 | −log₁₀(IC50 in molar) from ChEMBL; ≥ 5.0 means IC50 ≤ 10µM (active binder); null for STITCH-sourced or unassayed interactions |
| `retrieved_at`       | timestamptz           |       |

Unique constraint: `(compound_id, target_id)` — pair grain; `source_id` is an attribute, not part of the key.

---

## 5. Diseases

### `diseases`

| Column            | Type                  | Notes                                   |
| ----------------- | --------------------- | --------------------------------------- |
| `disease_id`      | PK                    |                                         |
| `canonical_key`   | text                  | unique                                  |
| `disease_name`    | text                  |                                         |
| `ontology_id`     | text                  | MeSH / DOID / UMLS / OMIM ID |
| `ontology_source` | text                  |                                         |
| `source_id`       | FK → `source_systems` |                                         |
| `source_url`      | text                  |                                         |
| `source_batch_id` | FK → `import_batches` |                                         |
| `retrieved_at`    | timestamptz           |                                         |

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

Unique constraint: `(disease_id, alias_key)` — one row per disease + slug; `alias_type` is an attribute. Index: `idx_disease_aliases_alias_key` on `alias_key`.

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
| `retrieved_at`      | timestamptz           |       |

Unique constraint: `(disease_id, target_id)` — pair grain; `source_id` is an attribute, not part of the key.

Index: `idx_disease_targets_score` on `score`.

---

## 6. Analysis runs

### `analysis_runs`

| Column          | Type            | Notes    |
| --------------- | --------------- | -------- |
| `analysis_id`   | PK              |          |
| `analysis_name` | text            |          |
| `disease_id`    | FK → `diseases` | optional |
| `notes`         | text            |          |
| `parameters`    | jsonb           |          |
| `status`          | text            |          |
| `current_stage`   | int             | null = not started, 1–8 during pipeline |
| `stage_results`   | jsonb NOT NULL  | per-stage intermediate results `{stage_1: {...}}`; default `{}` |
| `mode`            | text NOT NULL   | `auto` (end-to-end) or `guided` (pauses for approval per stage); default `auto` |
| `completed_at`    | timestamptz     |          |
| `expires_at`      | timestamptz     | null until complete; set to `completed_at + 24h`; GET returns 410 Gone after expiry; an hourly `pg_cron` job `purge-expired-analysis-runs` hard-deletes rows where `expires_at < now()` |
| `error_message`   | text            |          |
| `updated_at`      | timestamptz NOT NULL | last write timestamp; default `now()` |
| `created_at`      | timestamptz     |          |
| `created_by`      | text            |          |

Index: `idx_analysis_runs_status` on `status`.

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
  analysis_runs
```
