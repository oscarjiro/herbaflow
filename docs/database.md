# Database Schema

PostgreSQL via Supabase. All tables use snake_case. All timestamps are `timestamptz`.
13 tables total.

---

## Overview

| Group | Tables |
|---|---|
| Content-addressable entities | `plants`, `compounds`, `targets`, `diseases` |
| Alias children (1:m) | `plant_aliases`, `compound_aliases`, `target_aliases`, `disease_aliases` |
| Pair-grain junctions (m:m) | `plant_compounds`, `compound_targets`, `disease_targets` |
| Operational | `source_systems`, `analysis_runs` |

---

## Identity conventions

### UUID strategy

Entity PKs (`plant_id`, `compound_id`, `target_id`, `disease_id`) are UUID v5 derived
deterministically from `canonical_key` — there is no `DEFAULT gen_random_uuid()` on these
columns. The same input always produces the same UUID. Operational table PKs
(`source_systems.source_id`, `analysis_runs.analysis_id`) use UUID v4 via
`DEFAULT gen_random_uuid()`.

### Canonical keys

All canonical keys use `{source}:{id}` CURIE form. Examples:

| Entity | Canonical key form | Example |
|---|---|---|
| Plant | `gbif:{usageKey}` → `plant:{slug}` fallback | `gbif:2927065` |
| Compound | cascade: `inchikey:` > `pubchem:` > `chembl:` > `cas:` > `name_formula:` > `name:` > `formula:` | `inchikey:RYYVLZVUVIJVGH-UHFFFAOYSA-N` |
| Target | `uniprot:{acc}` (isoform-folded) → `ensembl:{id}` → `gene:{SYMBOL}` | `uniprot:P00533` |
| Disease | `doid:{id}` / `mesh:{id}` → `disease:{slug}` fallback | `doid:9352` |

Junction PKs key on `{left_id}:{right_id}` (pair grain). Alias PKs key on
`{parent_id}:{alias_key}`. `canonical_key` is also stored as a `UNIQUE` text column on each
entity table as a fast-lookup alternate key.

Every namespace, canonical-key cascade, and id builder lives in `etl/shared/identity.py`.
The backend mirrors the three IDs it mints (`compound_id`, `target_id`, `compound_target_id`)
in `backend/app/services/canonicalize.py`, kept byte-identical by parity tests.

### Per-row provenance

Each entity and junction row carries three provenance columns:

| Column | Purpose |
|---|---|
| `source_id` | FK → `source_systems`; identifies the source system |
| `source_url` | Per-row deep link to the exact source record (authoritative) |
| `retrieved_at` | Timestamp when the row was fetched |

An unknown `source_name` fails the ETL load — there is no silent NULL fallback.

---

## Naming conventions

| Pattern | Meaning |
|---|---|
| `*_id` | Stable primary key |
| `*_key` | Deduplication / lookup key (usually slugified) |
| `canonical_*` | Final accepted entity name or key |
| `*_aliases` | All non-canonical names for an entity |
| `source_name` | External system name (e.g. `KNApSAcK World`), never an entity name |
| `retrieved_at` | When the record was fetched from the source |
| `source_url` | Per-row deep link to the exact source record; authoritative provenance |

---

## Tables

### `source_systems`

One row per external data source. PKs are UUID v4.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `source_id` | uuid PK | NO | `DEFAULT gen_random_uuid()` |
| `source_name` | text | NO | e.g. `KNApSAcK World`, `GBIF`, `PubChem`, `UniProt`, `STRING` |
| `source_type` | text | NO | CHECK: `scrape` / `api` / `download` / `manual` |
| `base_url` | text | YES | Reference/fallback field; per-row `source_url` is authoritative |
| `notes` | text | YES | |

**Constraints:**
- PK: `source_systems_pkey` on `source_id`
- UNIQUE: `source_systems_source_name_key` on `source_name`
- CHECK `source_systems_source_type_check`: `source_type IN ('scrape', 'api', 'download', 'manual')`

**Indexes:**
- `source_systems_pkey` (unique, btree, `source_id`)
- `source_systems_source_name_key` (unique, btree, `source_name`)

---

### `plants`

One canonical row per accepted plant taxon.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `plant_id` | uuid PK | NO | UUID v5 from `canonical_key` |
| `canonical_key` | text | NO | UNIQUE; `gbif:{usageKey}` or `plant:{slug}` |
| `canonical_scientific_name` | text | YES | Cleaned accepted name only, no authorship |
| `family_name` | text | YES | |
| `source_id` | uuid FK → `source_systems` | YES | |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `plants_pkey` on `plant_id`
- UNIQUE: `plants_canonical_key_key` on `canonical_key`
- FK: `plants_source_id_fkey` → `source_systems(source_id)`

**Indexes:**
- `plants_pkey` (unique, btree, `plant_id`)
- `plants_canonical_key_key` (unique, btree, `canonical_key`)
- `plants_source_id_idx` (btree, `source_id`)

---

### `plant_aliases`

All alternate names for a canonical plant.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `alias_id` | uuid PK | NO | UUID v5 from `{plant_id}:{alias_key}` |
| `plant_id` | uuid FK → `plants` | NO | |
| `alias_name` | text | YES | Display form of the alias |
| `alias_key` | text | YES | Slugified; used as the UNIQUE grain |
| `alias_type` | text | YES | ETL-internal vocab: `normalized_variant`, `synonym_variant` (no DB CHECK) |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `plant_aliases_pkey` on `alias_id`
- UNIQUE: `plant_aliases_parent_key` on `(plant_id, alias_key)` — one row per plant + slug; `alias_type` is an attribute
- FK: `plant_aliases_plant_id_fkey` → `plants(plant_id)`

**Indexes:**
- `plant_aliases_pkey` (unique, btree, `alias_id`)
- `plant_aliases_parent_key` (unique, btree, `(plant_id, alias_key)`)
- `plant_aliases_plant_id_idx` (btree, `plant_id`)
- `plant_aliases_alias_key_idx` (btree, `alias_key`)

---

### `compounds`

One canonical row per chemical entity.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `compound_id` | uuid PK | NO | UUID v5 from `canonical_key` |
| `canonical_key` | text | NO | UNIQUE; cascade from `inchikey:` → … → `formula:` |
| `canonical_name` | text | YES | |
| `inchi_key` | text | YES | |
| `smiles` | text | YES | Canonical or isomeric SMILES |
| `cas_id` | text | YES | |
| `pubchem_cid` | text | YES | |
| `chembl_id` | text | YES | |
| `molecular_formula` | text | YES | |
| `molecular_weight` | double precision | YES | |
| `tpsa` | double precision | YES | Topological polar surface area |
| `logp` | double precision | YES | Calculated lipophilicity |
| `hbond_donors` | integer | YES | |
| `hbond_acceptors` | integer | YES | |
| `rotatable_bonds` | integer | YES | |
| `qed_score` | double precision | YES | Quantitative Estimate of Drug-likeness (0–1, higher = more drug-like); computed by RDKit |
| `np_likeness_score` | double precision | YES | Natural product-likeness score (RDKit); ≥ 0.5 triggers NP exception in ADME filtering |
| `num_ro5_violations` | integer | YES | Count of Lipinski Rule of Five violations; CHECK 0–4 |
| `is_pains_positive` | boolean | NO | DEFAULT `false`; PAINS flag (Baell & Holloway 2010); reporting only, not a filter |
| `source_id` | uuid FK → `source_systems` | YES | |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `compounds_pkey` on `compound_id`
- UNIQUE: `compounds_canonical_key_key` on `canonical_key`
- FK: `compounds_source_id_fkey` → `source_systems(source_id)`
- CHECK `compounds_num_ro5_violations_check`: `num_ro5_violations IS NULL OR (num_ro5_violations >= 0 AND num_ro5_violations <= 4)`

**Indexes:**
- `compounds_pkey` (unique, btree, `compound_id`)
- `compounds_canonical_key_key` (unique, btree, `canonical_key`)
- `compounds_inchi_key_idx` (btree, `inchi_key`)
- `compounds_pubchem_cid_idx` (btree, `pubchem_cid`)
- `compounds_chembl_id_idx` (btree, `chembl_id`)
- `compounds_source_id_idx` (btree, `source_id`)

---

### `compound_aliases`

All alternate names for a canonical compound.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `compound_alias_id` | uuid PK | NO | UUID v5 from `{compound_id}:{alias_key}` |
| `compound_id` | uuid FK → `compounds` | NO | |
| `alias_name` | text | YES | Display form |
| `alias_key` | text | YES | Slugified; used as the UNIQUE grain |
| `alias_type` | text | YES | ETL-internal vocab: `enrichment_synonym`, `source_compound_id`, `cas_id`, `canonical_name`, `raw_metabolite_name`, `iupac_name` (no DB CHECK) |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `compound_aliases_pkey` on `compound_alias_id`
- UNIQUE: `compound_aliases_parent_key` on `(compound_id, alias_key)`
- FK: `compound_aliases_compound_id_fkey` → `compounds(compound_id)`

**Indexes:**
- `compound_aliases_pkey` (unique, btree, `compound_alias_id`)
- `compound_aliases_parent_key` (unique, btree, `(compound_id, alias_key)`)
- `compound_aliases_compound_id_idx` (btree, `compound_id`)
- `compound_aliases_alias_key_idx` (btree, `alias_key`)

---

### `plant_compounds`

Pair-grain junction. Answers: which compounds were found in which plants?

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `plant_compound_id` | uuid PK | NO | UUID v5 from `{plant_id}:{compound_id}` |
| `plant_id` | uuid FK → `plants` | NO | |
| `compound_id` | uuid FK → `compounds` | NO | |
| `source_id` | uuid FK → `source_systems` | YES | Attribute; not part of pair grain |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `plant_compounds_pkey` on `plant_compound_id`
- UNIQUE: `plant_compounds_pair_key` on `(plant_id, compound_id)`
- FK: `plant_compounds_plant_id_fkey` → `plants(plant_id)`
- FK: `plant_compounds_compound_id_fkey` → `compounds(compound_id)`
- FK: `plant_compounds_source_id_fkey` → `source_systems(source_id)`

**Indexes:**
- `plant_compounds_pkey` (unique, btree, `plant_compound_id`)
- `plant_compounds_pair_key` (unique, btree, `(plant_id, compound_id)`)
- `plant_compounds_plant_id_idx` (btree, `plant_id`)
- `plant_compounds_compound_id_idx` (btree, `compound_id`)

---

### `targets`

Canonical protein/gene entities. All targets are human (NCBI taxonomy 9606) — organism taxon is a pipeline invariant and is not stored as a column.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `target_id` | uuid PK | NO | UUID v5 from `canonical_key` |
| `canonical_key` | text | NO | UNIQUE; `uniprot:{acc}` → `ensembl:{id}` → `gene:{SYMBOL}` |
| `gene_symbol` | text | YES | HGNC-approved symbol |
| `protein_name` | text | YES | |
| `uniprot_accession` | text | YES | Isoform-folded canonical accession |
| `source_id` | uuid FK → `source_systems` | YES | |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `targets_pkey` on `target_id`
- UNIQUE: `targets_canonical_key_key` on `canonical_key`
- FK: `targets_source_id_fkey` → `source_systems(source_id)`

**Indexes:**
- `targets_pkey` (unique, btree, `target_id`)
- `targets_canonical_key_key` (unique, btree, `canonical_key`)
- `idx_targets_gene_symbol` (btree, `gene_symbol`)
- `idx_targets_uniprot_accession` (btree, `uniprot_accession`)

Note: the legacy duplicate indexes `targets_gene_symbol_idx` and
`targets_uniprot_accession_idx` were dropped; only `idx_targets_gene_symbol` and
`idx_targets_uniprot_accession` remain.

---

### `target_aliases`

All alternate names for a canonical target.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `target_alias_id` | uuid PK | NO | UUID v5 from `{target_id}:{alias_key}` |
| `target_id` | uuid FK → `targets` | NO | |
| `alias_name` | text | YES | Display form |
| `alias_key` | text | YES | Slugified; used as the UNIQUE grain |
| `alias_type` | text | YES | ETL-internal vocab: `ensembl_id`, `approved_symbol`, `approved_name` (no DB CHECK) |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `target_aliases_pkey` on `target_alias_id`
- UNIQUE: `target_aliases_parent_key` on `(target_id, alias_key)`
- FK: `target_aliases_target_id_fkey` → `targets(target_id)`

**Indexes:**
- `target_aliases_pkey` (unique, btree, `target_alias_id`)
- `target_aliases_parent_key` (unique, btree, `(target_id, alias_key)`)
- `target_aliases_target_id_idx` (btree, `target_id`)
- `target_aliases_alias_key_idx` (btree, `alias_key`)

---

### `compound_targets`

Pair-grain junction. Answers: which targets are linked to which compounds?

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `compound_target_id` | uuid PK | NO | UUID v5 from `{compound_id}:{target_id}` |
| `compound_id` | uuid FK → `compounds` | NO | |
| `target_id` | uuid FK → `targets` | NO | |
| `source_id` | uuid FK → `source_systems` | YES | Attribute; not part of pair grain |
| `prediction_method` | text | YES | CHECK: `NULL` or `chembl_bioactivity` / `pubchem_bioassay` / `stp_import` |
| `score` | double precision | YES | Source-specific activity score |
| `pchembl_value` | double precision | YES | −log₁₀(IC50 in molar) from ChEMBL; ≥ 5.0 means IC50 ≤ 10µM; null for non-ChEMBL sources |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `compound_targets_pkey` on `compound_target_id`
- UNIQUE: `compound_targets_pair_key` on `(compound_id, target_id)`
- FK: `compound_targets_compound_id_fkey` → `compounds(compound_id)`
- FK: `compound_targets_target_id_fkey` → `targets(target_id)`
- FK: `compound_targets_source_id_fkey` → `source_systems(source_id)`
- CHECK `compound_targets_prediction_method_check`: `prediction_method IS NULL OR prediction_method IN ('chembl_bioactivity', 'pubchem_bioassay', 'stp_import')`

**Indexes:**
- `compound_targets_pkey` (unique, btree, `compound_target_id`)
- `compound_targets_pair_key` (unique, btree, `(compound_id, target_id)`)
- `compound_targets_compound_id_idx` (btree, `compound_id`)
- `compound_targets_target_id_idx` (btree, `target_id`)

---

### `diseases`

One canonical row per disease entity.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `disease_id` | uuid PK | NO | UUID v5 from `canonical_key` |
| `canonical_key` | text | NO | UNIQUE; `doid:{id}` / `mesh:{id}` → `disease:{slug}` fallback |
| `disease_name` | text | YES | Display field — case-preserved from the curated seed (e.g. `Type 2 Diabetes Mellitus`), single column. The lowercase ontology label lives in `disease_aliases`, not here. |
| `ontology_id` | text | YES | MeSH / DOID / UMLS / OMIM identifier |
| `ontology_source` | text | YES | e.g. `Disease Ontology`, `MeSH`; free text, no CHECK |
| `source_id` | uuid FK → `source_systems` | YES | |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `diseases_pkey` on `disease_id`
- UNIQUE: `diseases_canonical_key_key` on `canonical_key`
- FK: `diseases_source_id_fkey` → `source_systems(source_id)`

**Indexes:**
- `diseases_pkey` (unique, btree, `disease_id`)
- `diseases_canonical_key_key` (unique, btree, `canonical_key`)
- `diseases_ontology_id_idx` (btree, `ontology_id`)

---

### `disease_aliases`

All alternate names for a canonical disease.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `disease_alias_id` | uuid PK | NO | UUID v5 from `{disease_id}:{alias_key}` |
| `disease_id` | uuid FK → `diseases` | NO | |
| `alias_name` | text | YES | Display form |
| `alias_key` | text | YES | Slugified; used as the UNIQUE grain |
| `alias_type` | text | YES | ETL-internal vocab: `user_alias` (no DB CHECK) |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `disease_aliases_pkey` on `disease_alias_id`
- UNIQUE: `disease_aliases_parent_key` on `(disease_id, alias_key)`
- FK: `disease_aliases_disease_id_fkey` → `diseases(disease_id)`

**Indexes:**
- `disease_aliases_pkey` (unique, btree, `disease_alias_id`)
- `disease_aliases_parent_key` (unique, btree, `(disease_id, alias_key)`)
- `disease_aliases_disease_id_idx` (btree, `disease_id`)
- `idx_disease_aliases_alias_key` (btree, `alias_key`)

---

### `disease_targets`

Pair-grain junction. Answers: which targets are implicated in which diseases?

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `disease_target_id` | uuid PK | NO | UUID v5 from `{disease_id}:{target_id}` |
| `disease_id` | uuid FK → `diseases` | NO | |
| `target_id` | uuid FK → `targets` | NO | |
| `source_id` | uuid FK → `source_systems` | YES | Attribute; not part of pair grain |
| `association_type` | text | YES | Source-owned vocab; e.g. `open_targets_overall`; no DB CHECK |
| `score` | double precision | YES | Open Targets overall association score |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |

**Constraints:**
- PK: `disease_targets_pkey` on `disease_target_id`
- UNIQUE: `disease_targets_pair_key` on `(disease_id, target_id)`
- FK: `disease_targets_disease_id_fkey` → `diseases(disease_id)`
- FK: `disease_targets_target_id_fkey` → `targets(target_id)`
- FK: `disease_targets_source_id_fkey` → `source_systems(source_id)`

**Indexes:**
- `disease_targets_pkey` (unique, btree, `disease_target_id`)
- `disease_targets_pair_key` (unique, btree, `(disease_id, target_id)`)
- `disease_targets_disease_id_idx` (btree, `disease_id`)
- `disease_targets_target_id_idx` (btree, `target_id`)
- `idx_disease_targets_score` (btree, `score`)

---

### `analysis_runs`

One row per pipeline execution. PKs are UUID v4.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `analysis_id` | uuid PK | NO | `DEFAULT gen_random_uuid()` |
| `analysis_name` | text | YES | User-supplied label |
| `disease_id` | uuid FK → `diseases` | YES | The target disease for this run |
| `parameters` | jsonb | NO | Run-input snapshot (plants, compounds, targets, options); CHECK `jsonb_typeof = 'object'` |
| `status` | text | YES | Dynamic backend-set string: `pending`, `failed`, `complete`, `stage_{N}_running`, `stage_{N}_awaiting_approval`, `stage_{N}_starting`, `stage_{N}_rejected`; no fixed-vocab CHECK |
| `current_stage` | integer | YES | null = not started; 1–8 during pipeline; CHECK `NULL OR (1 <= current_stage <= 8)` |
| `stage_results` | jsonb | NO | Per-stage intermediate results keyed by stage number; default `{}`; CHECK `jsonb_typeof = 'object'` |
| `mode` | text | NO | CHECK: `auto` (end-to-end) or `guided` (pauses for approval per stage); contract source: `shared/contracts/analysis.json` |
| `created_at` | timestamptz | YES | |
| `completed_at` | timestamptz | YES | Set when pipeline finishes |
| `expires_at` | timestamptz | YES | Set to `completed_at + 24h`; GET returns 410 Gone after expiry |
| `error_message` | text | YES | |
| `updated_at` | timestamptz | NO | Last write timestamp |

**Run-input storage:** All run inputs (plant list, manual compounds, manual targets, disease
scope, validation options) are stored in `parameters` jsonb. The only relational link to an
entity table is `disease_id` FK. There are no separate run-input junction tables — they were
dropped and stay dropped. This means cascading deletes of the disease row would orphan runs;
guard accordingly.

**Constraints:**
- PK: `analysis_runs_pkey` on `analysis_id`
- FK: `analysis_runs_disease_id_fkey` → `diseases(disease_id)`
- CHECK `analysis_runs_mode_check`: `mode IN ('auto', 'guided')`
- CHECK `analysis_runs_current_stage_check`: `current_stage IS NULL OR (current_stage >= 1 AND current_stage <= 8)`
- CHECK `analysis_runs_parameters_object_check`: `jsonb_typeof(parameters) = 'object'`
- CHECK `analysis_runs_stage_results_object_check`: `jsonb_typeof(stage_results) = 'object'`

**Indexes:**
- `analysis_runs_pkey` (unique, btree, `analysis_id`)
- `idx_analysis_runs_status` (btree, `status`)
- `idx_analysis_runs_expires_at` (btree, `expires_at`)

---

## Security

### Row-Level Security

RLS is **enabled on all 13 tables** (`pg_class.relrowsecurity = true`). There are **no
permissive policies defined** in the `public` schema. This means all 13 tables are
deny-by-default: every row operation from the Supabase Data API (PostgREST / anon/authenticated
roles) is blocked unless a policy explicitly permits it.

The application accesses the database exclusively via the FastAPI backend using the
service-role key or a direct connection string — never through the Data API with the anon key.

### Data API

The Supabase Data API (PostgREST auto-generated REST endpoints) is **being disabled** as a
defense-in-depth measure on top of RLS. This is a Supabase dashboard setting. Intended state:
Data API disabled; all database access goes through the FastAPI backend only.

---

## Operational

### pg_cron: expired run purge

A pg_cron job runs hourly to hard-delete expired analysis runs:

| Property | Value |
|---|---|
| Job name | `purge-expired-analysis-runs` |
| Schedule | `0 * * * *` (top of every hour) |
| Command | `DELETE FROM analysis_runs WHERE expires_at IS NOT NULL AND expires_at < now()` |
| Active | yes |

Rows are eligible for deletion once `expires_at` is set (after completion) and the 24-hour
TTL has elapsed. The API returns 410 Gone for expired runs before the cron job removes them.

---

## Tables that do not exist

The following tables appear in some older documentation or planning notes but **do not exist
in the schema and are not part of the model:**

| Table | Status |
|---|---|
| `ppi_edges` | Never created; PPI data is computed at pipeline runtime, not persisted |
| `analysis_run_inputs` | Dropped; superseded by `analysis_runs.parameters` jsonb |
| `analysis_run_compounds` | Dropped; superseded by `analysis_runs.parameters` jsonb |
| `analysis_run_targets` | Dropped; superseded by `analysis_runs.parameters` jsonb |
| `source_snapshots` | Never created |
| `import_batches` | Never created |
| `api_cache` | Never created |

Run-input provenance (plant list, manual compounds, manual targets, disease scope, options)
lives entirely in `analysis_runs.parameters` jsonb plus the `disease_id` FK. The relational
run-input junction tables were dropped and stay dropped. Known limitation: querying "which
plants were used in which runs" requires parsing the jsonb rather than a join.

---

## Derived relationships (not stored)

These associations are query-derived through the graph, not stored as tables:

- Plant → Disease (via `plant_compounds` → `compound_targets` → `disease_targets`)
- Compound → Disease (via `compound_targets` → `disease_targets`)
- Plant → Target (via `plant_compounds` → `compound_targets`)

The pipeline traversal order is: `plants → compounds → targets → diseases → PPI network`.

---

## ETL build order

```
1. source_systems
2. plants, plant_aliases
3. compounds, compound_aliases
4. plant_compounds
5. targets, target_aliases
6. compound_targets
7. diseases, disease_aliases
8. disease_targets
9. analysis_runs  (created at runtime by the backend)
```

---

## Migrations

The schema is represented by a single clean ordered baseline in `supabase/migrations/`,
diff-verified schema-equivalent to the live database. It supersedes the earlier
incremental ledger.

```
20260608000001_baseline_extensions_functions.sql   rls_auto_enable() event-trigger function
20260608000002_baseline_entities.sql               plants, compounds, targets, diseases
20260608000003_baseline_aliases.sql                the four *_aliases tables
20260608000004_baseline_junctions.sql              plant_compounds, compound_targets, disease_targets
20260608000005_baseline_operational.sql            source_systems, analysis_runs
20260608000006_baseline_constraints_indexes_rls.sql  all foreign keys, indexes, ENABLE ROW LEVEL SECURITY
20260608000007_baseline_cron.sql                   pg_cron hourly purge of expired analysis_runs (platform-only)
```

Tables are created first and all foreign keys added last, so the set replays in order on a
fresh database. File `0007` requires the managed platform's `pg_cron`; the other six replay
on any stock PostgreSQL (used for the equivalence check).

