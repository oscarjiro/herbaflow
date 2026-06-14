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
| `source_name` | text | NO | e.g. `KNApSAcK World`, `GBIF`, `PubChem`, `UniProt`, `STRING`, `Manual Entry` |
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

The `Manual Entry` row (`source_type = 'manual'`, `base_url` null) is seeded so user-entered
compounds satisfy the `source_id` FK; their per-row `source_url` is null (no external deep link).

Stage 3 (compound→target) attributes edges and target rows to four sources. `ChEMBL`,
`UniProt`, and `PubChem` already exist; `PubChem BioAssay` (`api`; distinct from `PubChem`,
which serves compound structures) and `SwissTargetPrediction` (`manual`; seeded but no longer
used for edges — STP paste-back is run-scoped, see `compound_targets`) are seeded by
`20260610000001_seed_target_sources.sql`.

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
| `validation_status` | text | NO | DEFAULT `externally_validated`; `externally_validated` = backed by DB/PubChem (and all ETL rows); `structure_only` = RDKit-derived identity from a manually entered SMILES with no external match (descriptors null until ADME runs) |

**Constraints:**
- PK: `compounds_pkey` on `compound_id`
- UNIQUE: `compounds_canonical_key_key` on `canonical_key`
- FK: `compounds_source_id_fkey` → `source_systems(source_id)`
- CHECK `compounds_num_ro5_violations_check`: `num_ro5_violations IS NULL OR (num_ro5_violations >= 0 AND num_ro5_violations <= 4)`
- CHECK `compounds_validation_status_check`: `validation_status IN ('externally_validated', 'structure_only')`

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
| `prediction_method` | text | YES | CHECK below. Only `chembl_bioactivity` / `pubchem_bioassay` are written; `stp_import` is **legacy** — the CHECK still permits it, but STP is now run-scoped and writes no edge (see precedence rule) |
| `score` | double precision | YES | Source-specific activity score |
| `pchembl_value` | double precision | YES | −log₁₀(IC50 in molar) from ChEMBL; ≥ 5.0 means IC50 ≤ 10µM; null for non-ChEMBL sources |
| `source_url` | text | YES | Per-row deep link; authoritative |
| `retrieved_at` | timestamptz | YES | |
| `min_pchembl` | double precision | YES | Stage-3 discovery threshold that produced this edge (D9 reuse key); null = legacy/unknown |
| `min_assay_confidence` | integer | YES | Stage-3 ChEMBL assay-confidence floor at discovery (D9 reuse key — not re-derivable from the edge); null = legacy/unknown |

**Reuse (D9):** Stage 3 reuses a compound's persisted edges instead of re-calling ChEMBL/PubChem/UniProt when the run's discovery params are compatible. It **replaces** (deletes then re-inserts) a compound's edge set on fetch, so all of a compound's edges share one `(min_pchembl, min_assay_confidence)` pair; it reuses cached edges only when `min_assay_confidence` matches exactly and `min_pchembl` is equal-or-looser than the run's (then re-filters `pchembl_value >= min_pchembl`; PubChem edges, which have no pchembl, are always kept). Null discovery params → refetch. Limitations: a compound resolving to **zero** targets carries no edges → it re-resolves every run; a DB error mid-replace could leave a partial set (narrow, self-heals on the next refetch).

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

**Edge precedence rule:** `chembl_bioactivity` > `pubchem_bioassay`. A measured upsert (ChEMBL or
PubChem BioAssay) overwrites the lower-precedence edge for the same (compound, target) pair on
re-run (idempotent). **SwissTargetPrediction (STP) paste-back and manual target adds write NO edge**
— their resolved targets are run-scoped only (the run's Stage-3 set), since a user-asserted,
unverifiable link must never be canonical (B4). The `stp_import` value is kept in the CHECK for any
legacy rows but is no longer produced (revised 2026-06-10).

**Provenance:** ChEMBL edges carry a `source_url` deep-link to the ChEMBL activity record; PubChem
BioAssay edges link to the BioAssay page. No `stp_import` edges are written; the seeded
`SwissTargetPrediction` source row is retained but unused for edges.

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
| `opentargets_score` | double precision | YES | Open Targets overall association score |
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
- `idx_disease_targets_score` (btree, `opentargets_score`)

**Pipeline read (Step 4):** Stage 4 (disease→target collection) is a **filtered read** of this
table — not a live Open Targets call. Open Targets is an ETL-time source (analogous to KNApSAcK on
the compound side); Step 4 reads the seeded snapshot. The read filters `opentargets_score >= min_score`
(contract default 0.3), joins `targets` for the gene symbol / accession / protein name, and orders
by `opentargets_score` descending (`idx_disease_targets_score`). It reads the run's `analysis_runs.disease_id`;
targets are human-only (9606), fixed. An empty result (filter too strict or thin ETL coverage) is
weak-but-valid — Step 4 proceeds to its approval checkpoint with a count-0 honesty note, it does
**not** hard-stop. The per-row link surfaced in the UI is the joined Target's UniProt deep link
(`targets.source_url`).

**Manual disease-target adds write NO edge.** A manual disease-target addition goes through the
shared manual target-add path (resolved via `POST /targets/validate`, applied via
`POST /analyses/{id}/stages/4/edit`): it persists the **Target** entity (canonical row) but writes
**no `disease_targets` row** — the disease→target relationship is run-scoped only (Software Lock
§6.2-E: added entities persist as canonical rows but not as relationships, since a user-asserted,
unverifiable disease link must never be canonical). Manual disease-targets therefore carry **no
association score**.

---

### `analysis_runs`

One row per pipeline execution. PKs are UUID v4.

| Column | Type | Nullable | Notes |
|---|---|---|---|
| `analysis_id` | uuid PK | NO | `DEFAULT gen_random_uuid()` |
| `analysis_name` | text | YES | User-supplied label |
| `disease_id` | uuid FK → `diseases` | YES | The target disease for this run |
| `parameters` | jsonb | NO | Run-input snapshot (plants, compounds, targets, options); CHECK `jsonb_typeof = 'object'` |
| `status` | text | YES | Dynamic backend-set string: `pending`, `failed`, `complete`, `stage_{N}_running`, `stage_{N}_awaiting_approval`, `stage_{N}_starting`; no fixed-vocab CHECK |
| `current_stage` | integer | YES | null = not started; 1–8 during pipeline; CHECK `NULL OR (1 <= current_stage <= 8)` |
| `stage_results` | jsonb | NO | Per-stage intermediate results keyed by stage number; default `{}`; CHECK `jsonb_typeof = 'object'` |
| `mode` | text | NO | DEFAULT `guided`; CHECK: `auto` (end-to-end) or `guided` (pauses for approval per stage); contract source: `shared/contracts/analysis.json` |
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

#### `parameters` jsonb shape

```jsonc
{
  "plant_ids":        ["<uuid>", ...],          // selected plant UUIDs (selection mode only; [] in manual modes)
  "manual_compounds": ["<uuid>", ...],          // pre-resolved compound UUIDs injected into Stage 1
  "stage_edits": {                              // durable in-stage add/remove decisions; keyed by stage number string
    "<stage>": {
      "added":   [{"compound_id": "<uuid>", "canonical_name": "<str|null>"}, ...],
      "removed": ["<uuid>", ...]
    }
    // ...
  },
  "input_modes": {                              // stamped at create; ABSENT on pre-feature runs → treated as selection/selection
    "plant":    "selection | manual_compounds | manual_targets",
    "disease":  "selection | manual_disease_targets"
  },
  "labels": {                                   // display-only free text (≤200 chars); present only when a manual mode supplied a label
    "plant":   "<str>",                         // NEVER canonicalized, NEVER used as an identity
    "disease": "<str>"
  },
  "adme": { /* frozen ADME parameters; see below */ }
  // further param groups: "target", "disease_targets", "ppi", "hub_genes", "enrichment"
}
```

`stage_edits` is normalized: an id is never in both `added` and `removed` simultaneously (re-adding
clears a pending removal; re-removing clears a pending add). The edit layer is **durable** — it
survives a re-run's clear of `stage_results` and is reapplied every time the stage recomputes.
Defaults for each param-bearing stage are frozen into `parameters` at run-creation time; a Redo
overrides them within the contract's hard bounds.

`parameters.stage_edits` may be **seeded at run-creation** for manual input modes: Stage 1 (manual
compound IDs seeded into the S1 entity layer), Stage 3 (manual plant targets), and Stage 4 (manual
disease targets). Previously, `stage_edits` was only ever written by in-stage edit calls;
manual input modes write it at create time so the pipeline's edit-layer reapplication logic is
reused without special-casing.

`parameters.input_modes` is absent on runs created before this feature was introduced; the
backend treats absent `input_modes` as `{plant: "selection", disease: "selection"}` (fully
backward compatible). `parameters.labels` is absent when no manual mode supplied a label.

**Manual entities and catalog rows:** manual plant and disease entities supplied via a manual input
mode create **no catalog row** — there is no `plants` row and no `diseases` row for a free-text
manual plant or disease. The pipeline operates entirely on the run's `stage_results` and
`stage_edits`. For `manual_disease_targets` mode, `analysis_runs.disease_id` is **NULL** (the
column was already a nullable FK; no schema migration required). All of the above lives in the
existing jsonb columns; no schema migration is needed for any input-modes field.

#### `stage_results` jsonb shape

Keyed by stage number string (e.g. `"1"`, `"2"`).

**Entity stages** (e.g. Stage 1 — compound selection):

```jsonc
{
  "compounds": [
    {"compound_id": "<uuid>", "canonical_name": "<str|null>", "tag": "<tag>"},
    // tag ∈ {"computed", "user-added", "user-removed"}
    // "user-removed" entries are PRESENT in this list but excluded from the effective forward set
    ...
  ],
  "computed_ids": ["<uuid>", ...],   // the raw runner output before edit-layer application
  "count": <int>,                    // effective count (excludes "user-removed"); 0 hard-stops the run
  "state": "<stage_state>",          // "computed" | "user_provided" | "not_applicable"
  "per_plant": { "<plant_id>": ["<compound_id>", ...], ... }  // Stage 1 only
}
```

`state` values:
- `"computed"` — the stage ran normally (no or empty edit layer).
- `"user_provided"` — the stage was pre-filled by the user via a manual input mode (seeded via
  `stage_edits` at create time) **or** the user later edited the computed result (non-empty edit
  layer). Both produce the same state marker.
- `"not_applicable"` — the stage does not apply to the chosen input mode. Pre-filled at create
  as `{"state": "not_applicable", "count": 0}` (e.g., Stage 1 compound lookup in
  `manual_targets` mode, or Stage 4 disease-target DB read in `manual_disease_targets` mode).
  Downstream stages treat this as an empty-but-valid input; it does **not** hard-stop the run.

**Stage 1 jsonb notes:**
- `stage_results["1"].compounds[*].canonical_name` is populated from the compound row on a
  `manual_compounds` prefill (was previously `null` — Stage 1 was showing the UUID). Display only;
  no schema change. Symmetric with the Stage-3 target prefill which already carried names.
- The `POST /compounds/validate` response `FailedInput` objects carry an optional 1-based **`line`**
  field on compound failures (parity with `resolve_targets` which already reported line indices;
  Software Lock §4.5 per-line reason). No schema change — the `line` field is in the response body
  only, not persisted to `stage_results` or `parameters`.
- **No migration** — all of the above is display / CSV / response-body only; no column or jsonb
  structure change.

**Stage 4 (`stage_results["4"]`) shape — ONE enriched `targets` list:**

Stage 4 emits a single edit-layer `targets` list; each row carries the Open Targets association
fields. There is **no separate `disease_targets` view list** — the edit layer preserves every field
on each row, so the disease association `opentargets_score` survives a post-create Stage-4 edit and reaches
Stage 5 / is ranked by Stage 6 (B-DUP-2/L-11; previously a second view list was folded separately
and never saw edits):

```jsonc
{
  "state": "computed | user_provided",
  "count": <int>,
  "min_score_applied": <float|null>,       // null for a manual (user_provided) Stage 4
  "targets": [
    {
      "target_id": "<uuid>",
      "canonical_name": "<str>",           // gene_symbol -> uniprot_accession -> target_id
      "gene_symbol": "<str|null>",
      "uniprot_accession": "<str|null>",
      "opentargets_score": <float|null>,     // Open Targets association score (DT4-9)
      "association_type": "<str|null>",
      "source_url": "<str|null>",          // UniProt deep link
      "tag": "computed | user-added | user-removed"
    }
  ]
}
```

Stage 5 intersects this list (excluding `user-removed` rows on both sides) against the Stage-3 set
on `target_id`, carrying the `opentargets_score` into the overlap. A **manually-added** disease target has no
disease edge: its `opentargets_score`/`association_type` are absent (consumers use `.get`) — there is **no
association score** for a manual target (no `disease_targets` table edge; the link is run-scoped
only — see the `disease_targets` table note above) — but it still carries the UniProt `source_url`
so the FE table and CSV match a computed row.

**ADME stage** (Stage 2):

```jsonc
{
  "passed": [
    {
      "compound_id": "<uuid>", "canonical_name": "<str|null>",
      "descriptor_source": "etl|rdkit|unscreened",
      "molecular_weight": <float|null>, "logp": <float|null>,
      "hbond_donors": <int|null>, "hbond_acceptors": <int|null>,
      "tpsa": <float|null>, "rotatable_bonds": <int|null>,
      "qed_score": <float|null>, "np_likeness_score": <float|null>,
      "num_ro5_violations": <int|null>, "is_pains_positive": <bool>,
      "source_url": "<str|null>",
      "badges": ["pains", "np_bypass", "unscreened"]   // only relevant badges present
    },
    ...
  ],
  "filtered": [
    { /* same descriptor fields */ , "reason": "<str>" },
    // reason examples: "2 Lipinski violation(s)", "fails Veber: TPSA", "could not screen"
    ...
  ],
  "annotations": {
    "pains":           ["<compound_id>", ...],   // annotated on screened compounds; NEVER a filter
    "np_bypass":       ["<compound_id>", ...],
    "unscreened":      ["<compound_id>", ...],
    "could_not_screen":["<compound_id>", ...]
  },
  "count": <int>,       // len(passed); 0 triggers zero-pass handling (see gate semantics below)
  "state": "computed"   // ADME stage has no edit layer
}
```

`descriptor_source` values:
- `"etl"` — descriptors read from the database columns (seeded by ETL/PubChem).
- `"rdkit"` — descriptors computed on-the-fly via RDKit from the compound's SMILES (manual/null path);
  persisted back to the `compounds` table after computation.
- `"unscreened"` — `skip_adme` was on; no descriptor access took place.

**Overlap stage** (Stage 5 — no parameters):

```jsonc
{
  "overlap": [
    {"target_id": "<uuid>", "gene_symbol": "<str|null>",
     "uniprot_accession": "<str|null>", "opentargets_score": <float|null>},
    ...
  ],
  "count": <int>,                  // overlap size |A∩B|; 0 = terminal hard-stop (BOTH modes)
  "compound_target_count": <int>,  // |Stage-3 target set| (|A|)
  "disease_target_count": <int>,   // |Stage-4 target set| (|B|)
  "unmapped_count": <int>,         // overlap targets with no gene_symbol (cannot go to STRING)
  "state": "computed",
  "flags": [ /* "unmapped_targets" */ ]
}
```

Stage 5 is a **pure set intersection** of the Stage-3 compound-target set and the Stage-4
disease-target set on the canonical `target_id` (both columns are FKs to `targets.target_id`) — the
field-standard raw overlap (à la Venny/jvenn); no statistics, no parameters, no external API. The two
side-counts (`compound_target_count`, `disease_target_count`) are descriptive set sizes. A **0-overlap
result is a terminal scientific hard-stop in both guided and auto modes** (the run fails — there is
nothing downstream to build).

**PPI stage** (Stage 6 — STRING network; `parameters.ppi`).


Computed result:

```jsonc
{
  "state": "computed",
  "nodes": [{"gene_symbol": "<str>", "string_id": null}, ...],   // the mappable input genes
  "edges": [{"source": "<gene>", "target": "<gene>", "confidence": <float 0–1>}, ...],
  "node_count": <int>, "edge_count": <int>,
  "min_confidence": <float>, "network_type": "functional|physical",
  "unmapped": [],
  "capped": {"applied": <bool>, "max_proteins": <int>, "ranked_by": "opentargets_score"},
  "count": <int>,                  // = node_count
  "flags": [ /* "sparse_or_empty_network" */ ]
}
```

Blocked result (overlap exceeds `max_proteins` with `allow_top_n_cap` off):

```jsonc
{"blocked": true, "reason": "overlap_too_large", "overlap_count": <int>, "max_proteins": <int>}
```

The blocked marker drives the AD-6 mechanism: a **guided** run parks at the Stage-6 checkpoint (the
UI prompts to enable the top-N cap or narrow the inputs); an **auto** run hard-fails. Recover by
Redoing Stage 6 with `allow_top_n_cap: true` (proceeds on the top-N overlap targets ranked by
`opentargets_score`) or by raising `max_proteins`. Community/module detection is deferred
(future work) — Stage 6 delivers the PPI-source network only.

**Hub-genes stage** (Stage 7 — `parameters.hub_genes`).

```jsonc
"7": {
  "state": "computed",
  "hubs": [
    { "rank": 1, "target_id": "<uuid>", "gene_symbol": "TNF",
      "degree": 0.41, "betweenness": 0.33, "closeness": 0.58, "eigenvector": 0.29,
      "composite": 0.37, "source_url": "https://www.uniprot.org/uniprotkb/<acc>/entry" }
  ],
  "ranking_metric": "hub_bottleneck_composite",  // or "degree" when use_hub_bottleneck=false
  "composite_weight": 0.5, "normalization": "min_max",
  "node_count": <int>, "top_n": <int>, "count": <int>,  // count = hubs reported
  "flags": [ /* "network_too_small" | "eigenvector_fallback" */ ]
}
```

Stage 7 ranks the Stage-6 PPI proteins by four networkx centralities (degree/betweenness/
closeness/eigenvector, undirected graph) and a min-max hub-bottleneck composite
(`w·degree + (1−w)·betweenness`, Yu 2007). `top_n` is a descriptive cut, not a significance
test. Tiny/sparse networks are flagged (reported, never a hard-stop).

**Enrichment stage** (Stage 8 — `parameters.enrichment`; TERMINAL).

```jsonc
"8": {
  "state": "computed",
  "terms": [
    { "source": "KEGG", "term_id": "KEGG:04151", "name": "PI3K-Akt signaling pathway",
      "p_value": 3.1e-6, "term_size": 354, "query_size": 118, "intersection_size": 22,
      "intersection": ["AKT1", "TNF", "IL6"] }
  ],
  "input_gene_count": <int>, "background_gene_count": <int>,
  "background_source": "compound_target_universe",
  "correction": "fdr", "significance_threshold": 0.05, "min_term_size": 5, "no_iea": false,
  "sources": ["GO:BP","GO:MF","GO:CC","KEGG"],
  "degraded": false, "count": <int>,  // count = enriched terms (0 = honest null, still complete)
  "flags": [ /* "empty_input" | "no_enriched_terms" | "source_degraded" */ ]
}
```

Stage 8 enriches the Stage-5 overlap gene symbols against the **Stage-3 compound-target
universe** gene symbols (custom statistical background — method, not config) via g:Profiler
(GO + KEGG, cumulative hypergeometric, `p_value` already corrected). `min_term_size` is filtered
client-side. Empty input → honest null; a g:Profiler outage **degrades** (no terms) but the run
**still completes** — Stage 8 is the terminal stage, so its completion marks the run `complete`
and sets `completed_at`. A 0-term result is a valid completion, never an empty-gate stop.

---

#### ADME parameters and gate semantics

##### `parameters.adme` block

The `adme` object is frozen from the contract defaults at run-creation. Fields in the contract carry:

- A `default` value (frozen at create time).
- A human-readable `description` (shown in the UI param panel).
- **Two-tier bounds:** hard `minimum`/`maximum` (or `exclusiveMinimum`) enforce only
  physically-impossible values and are validated by the backend on every Redo. Advisory
  `recommended_min`/`recommended_max` define the literature-tunable range shown in the UI
  but are **never enforced** by the backend.
- Booleans carry only `default` + `description` (no range bounds).

Current `adme` parameters (all sourced from `shared/contracts/analysis.json`):

| Parameter | Type | Default | Hard bounds | Recommended range | Notes |
|---|---|---|---|---|---|
| `max_mw` | number | 500 | >0, ≤2000 | 350–600 | Molecular weight ceiling (Da) |
| `max_logp` | number | 5 | ≥−10, ≤20 | 3–5.6 | Lipophilicity ceiling |
| `max_hbd` | integer | 5 | ≥0, ≤50 | 3–5 | H-bond donor ceiling |
| `max_hba` | integer | 10 | ≥0, ≤50 | 8–10 | H-bond acceptor ceiling |
| `max_tpsa` | number | 140 | ≥0, ≤500 | 90–140 | TPSA ceiling (Å²); Veber criterion |
| `max_rotatable_bonds` | integer | 10 | ≥0, ≤50 | 7–10 | Rotatable-bond ceiling; Veber criterion |
| `apply_veber` | boolean | true | — | — | Enable Veber (TPSA + rotatable bonds) gate |
| `np_exception_threshold` | number | 0.5 | ≥−5, ≤5 | −1–2 | Ertl NP-likeness score at/above which NP bypass fires |
| `apply_np_exception` | boolean | true | — | — | Enable NP-likeness exception; off = strict (no NP rescue) |
| `max_violations` | integer | 1 | ≥0, ≤4 | 0–2 | Max Lipinski criteria a compound may break and still pass |
| `skip_adme` | boolean | false | — | — | Bypass ADME entirely; all compounds pass as "unscreened" |

##### Per-compound ADME gate (strict precedence — do not reorder)

1. **`skip_adme` on** → compound passes, badged `"unscreened"`. Operational opt-out; overrides
   everything.
2. **Descriptors unavailable** (manual compound whose SMILES will not compute, or a seeded row
   missing a required descriptor) → compound excluded, reason `"could not screen"`. This is a data
   gap, not a verdict.
3. **`apply_np_exception` AND `np_likeness_score >= np_exception_threshold`** → compound passes,
   badged `"np_bypass"`. Overrides **both** Lipinski and Veber.
4. **Rule gate:** count the four Lipinski criteria violated (MW / logP / HBD / HBA). Must be
   `<= max_violations`. If `apply_veber`, **both** Veber criteria (rotatable bonds AND TPSA) must
   pass — Veber is a hard conjunctive gate; one Veber violation filters. Failure reason distinguishes
   Lipinski vs Veber.
5. **PAINS** — annotated on every screened compound (badge `"pains"` on passed rows) but **never
   affects pass/fail**.

##### Deviations from the original parameter spec (record for collaborators)

- **`skip_adme` replaces `apply_adme_to_manual`** — one unified, all-or-nothing opt-out. The
  per-source granularity (ADME on manual vs seeded) was dropped by choice; there is a single bypass
  switch that applies to the whole screening run.
- **`max_violations` was added** (absent from the original contract). It is scoped to the **four
  Lipinski criteria only** — Veber's two criteria are not summed into this budget.
- **Lipinski is always on** — there is no Lipinski toggle. `apply_veber` extends the gate; it does
  not replace Lipinski.
- **Veber is a hard conjunctive gate** when enabled — both rotatable-bonds and TPSA must pass; there
  is no Veber violation budget.
- **`apply_np_exception`** is a new boolean (default on); setting it off means strict mode — no NP
  rescue regardless of score.
- **`np_exception_threshold` bounds corrected** from the original `0..1` to hard `−5..5` (the Ertl
  score's actual scale) with recommended `−1..2`.

---

#### `parameters.ppi` block (Stage 6)

Frozen from the contract defaults at run-creation (like `adme`). Two of the four are enum-bounded
and render as selects in the UI:

| Parameter | Type | Default | Bounds / enum | Notes |
|---|---|---|---|---|
| `min_confidence` | number | 0.4 | enum {0.15, 0.4, 0.7, 0.9} | STRING edge-confidence floor → `required_score = round(× 1000)` |
| `max_proteins` | integer | 2000 | ≥50, ≤2000 (rec. 200–2000) | Self-imposed STRING ceiling; over it requires `allow_top_n_cap` |
| `allow_top_n_cap` | boolean | false | — | Proceed on the top-N overlap targets (by disease score) when over the ceiling |
| `network_type` | string | functional | enum {functional, physical} | STRING network: all association evidence vs binding-only |

`min_confidence` carries no hard `minimum`/`maximum` (the UI restricts it to the tiers; the backend
accepts any number). `network_type` IS enum-validated on Redo — a string outside the closed
vocabulary is rejected **422**. The original `community_resolution` param (module detection) was
dropped; module detection is deferred future work.

---

#### `parameters.hub_genes` block (Stage 7)

Frozen from the contract defaults at run-creation (like `adme` and `ppi`). `normalization` is
hardcoded `"min_max"` — not a user param; `use_hub_bottleneck` drives the ranking metric.

| Parameter | Type | Default | Bounds / enum | Notes |
|---|---|---|---|---|
| `top_n` | integer | 10 | ≥1, ≤100 (rec. 5–20) | Descriptive hub cut; not a significance test |
| `use_hub_bottleneck` | boolean | true | — | Use composite hub-bottleneck (`w·degree+(1−w)·betweenness`); false = degree only |
| `composite_weight` | number | 0.5 | ≥0, ≤1 (rec. 0.3–0.7) | Weight `w` on degree in the composite; `(1−w)` on betweenness |

Min-max normalization is a fixed method constant, not configuration. Tiny/sparse networks (fewer
nodes than the minimum required for eigenvector convergence) emit the `"network_too_small"` flag
and fall back to degree-only — reported, never a hard-stop.

---

#### `parameters.enrichment` block (Stage 8)

Frozen from the contract defaults at run-creation. `sources` is stored but its UI multi-select is
deferred to Phase 5 — the Stage-8 param panel exposes only the three scalar params below.
Background is hardcoded to the Stage-3 compound-target universe (custom statistical background —
method constant, not configuration).

| Parameter | Type | Default | Bounds / enum | Notes |
|---|---|---|---|---|
| `significance_threshold` | number | 0.05 | >0, ≤1 (rec. 0.01–0.1) | Corrected-p significance cutoff for enriched terms (applies to whichever correction method is selected) |
| `min_term_size` | integer | 5 | ≥1, ≤500 (rec. 3–20) | Minimum gene-set size; filtered client-side from g:Profiler results |
| `correction` | string | `fdr` | enum {`fdr`, `g_SCS`, `bonferroni`} | Multiple-testing correction method; default BH-FDR; `g_SCS` = g:Profiler's adaptive threshold |
| `sources` | array | `["GO:BP","GO:MF","GO:CC","KEGG"]` | enum items {`GO:BP`,`GO:MF`,`GO:CC`,`KEGG`,`REAC`,`WP`} | Annotation vocabularies; Reactome (REAC) + WikiPathways (WP) additionally selectable; multi-select UI deferred to Phase 5 |
| `no_iea` | boolean | false | — | Exclude GO terms supported only by electronic (IEA) annotation |

`correction` defaults to `fdr` (BH-FDR); the `g_SCS` enum value uses g:Profiler's verbatim API
spelling. `sources` IS enum/array-validated on Redo — elements outside the closed vocabulary are
rejected **422**.

---

#### Dependency DAG and re-run rules

Re-runs follow a **dependency DAG**, not raw stage numbering:

```
S1 → S2 → S3 ─┐
               ├─→ S5 → S6 → S7
S4 ────────────┘    └──────→ S8
```

`S1→S2→S3` and `S4` both feed `S5`; `S5` feeds `S6` and `S8`; `S6` feeds `S7`; `S7` and `S8` are
parallel leaves.

**Closure examples by reset-from stage:**

| `reset-from/N` | Re-runs (closure ∩ runnable) |
|---|---|
| `reset-from/1` | S1, S2, S3, S5, S6, S7, S8 (not S4) |
| `reset-from/2` | S2, S3, S5, S6, S7, S8 (not S4) |
| `reset-from/3` | S3, S5, S6, S7, S8 (not S4) |
| `reset-from/4` | S4, S5, S6, S7, S8 |
| `reset-from/5` | S5, S6, S7, S8 |
| `reset-from/6` | S6, S7 (not S8 — S8 depends on S5, not S6) |
| `reset-from/7` | S7 only |
| `reset-from/8` | S8 only |

**Param Redo** (changing a param-bearing stage's parameters via `POST /analyses/{id}/reset-from/{stage}`
with a `param_overrides` body): re-runs **that stage plus its downstream closure** (the stage itself
is inclusive). A no-op Redo (overrides equal the current frozen values) returns immediately without
clearing or re-running.

**Set edit** (adding/removing entities on an entity stage via `POST /analyses/{id}/stages/{stage}/edit`):
**stages** the change — it re-derives the edited stage in place, flags the produced downstream stages
`stale`, and re-runs **nothing**. The subsequent `reset-from` is the sole recompute; it re-runs the
runnable members of the dependency closure, **exclusive** of the edited stage (editing Step-1
compounds → the closure re-run starts at Step 2). Because the edited stage is never recomputed by a
set edit (only its downstream closure is), this works for **user-provided (frozen) entity stages**
too: editing manual compounds / manual targets / manual disease-targets and re-running recomputes
the overlap onward — the recovery path for a 0-overlap `failed` run. (A **param** Redo of a frozen
stage stays rejected — a user-provided stage has no parameters to recompute.)

**Closure, not a linear range (F3):** a re-run executes exactly the runnable members of the
dependency *closure* — never "every later-numbered stage". Because Stage 4 (disease targets) is an
independent root, a compound-chain edit or a Step-2/3 Redo re-runs `{…, 5, 6}` but **not** Stage 4;
conversely a Stage-4 Redo re-runs `{5, 6}` without touching the compound chain.

Both `reset-from` and stage-edit are rejected with **409 Conflict** unless the run is settled
(`*_awaiting_approval` / `complete` / `failed`). `reset-from` is destructive: the downstream
`stage_results` are cleared **before** re-running (idempotent on outage).

**Edit layer durability:** `parameters.stage_edits` persists across re-runs. When a stage
recomputes, the edit layer is reapplied over the fresh result — manual curation is never silently
lost.

**Entity caps** — the following hard limits are sourced from the contract; overflow raises **422**
with the cap and the current count (no silent truncation):

| Entity | Cap |
|---|---|
| Compounds | 2,000 |
| Targets | 5,000 |
| Plants | 20 |

An edit that empties an entity stage triggers the same hard-stop as a computed-empty stage.

**Zero-pass at Step 2:**
- In **guided** mode — surfaces as the normal Step-2 approval checkpoint; a looser Redo or
  enabling `skip_adme` recovers the run.
- In **auto** mode — hard-stops the run with a recoverable empty-state error message.

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

## Results-handoff export (read-only)

The capstone export (`GET /analyses/{id}/export`, available only when `analysis_runs.status =
'complete'`) is a **pure read** of the run's persisted `analysis_runs.stage_results` jsonb plus a
batch lookup of the referenced `compounds` / `targets` rows. It adds **no table, no column, and no
migration** — it reshapes data that already exists. The bundle (one zip) holds four artifacts:

| Artifact | Built from | Shape |
|---|---|---|
| `ctp-nodes.csv` | `stage_results` 5 (overlap), 7 (hubs), 3 (compound_targets), 8 (terms) | `id, label, type, inchikey, uniprot_accession, is_hub, source` — one row per compound / target / pathway node. Compounds are those with a Stage-3 edge **into** a Stage-5 overlap target; targets are the overlap set (`is_hub` flags the Stage-7 hubs); pathways are the Stage-8 enriched terms. |
| `ctp-edges.csv` | `stage_results` 3 + 5 + 8 | `source, target, interaction, prediction_method, p_value` — compound→target edges into the overlap (carry the winning `prediction_method`) and target→pathway edges from each term's `intersection` gene list (carry the corrected `p_value`). |
| `docking.csv` | `stage_results` 7 + 3 + `targets` | `hub_gene_symbol, hub_uniprot_accession, alphafold_id, compound_name, compound_inchikey, compound_smiles, prediction_method` — one row per Stage-7 hub × binding compound. **`alphafold_id` = the hub's UniProt accession** (AlphaFold is keyed by accession; PDB structure ids are deferred). |
| `report.md` | `run_meta` + `parameters` + `stage_results` + labels | Markdown: run identity, opaque input labels (plant/disease; may be `N/A`), frozen parameters, per-stage counts, and a provenance note. |

**Provenance is labels-only.** The report records *when* data was fetched (`source_systems` names
+ per-stage `source_url`s) and links to each record, but **not** which external release produced it
— there is no `source_snapshots` table (see "Tables that do not exist") and the export does not add
one. This is a documented limitation, stated in `report.md` itself.

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

Later migrations (applied on top of the baseline):

```
20260609000001_compound_validation_status.sql      compounds.validation_status + Manual Entry source + guided default
20260610000001_seed_target_sources.sql             PubChem BioAssay + SwissTargetPrediction source rows
```

Tables are created first and all foreign keys added last, so the set replays in order on a
fresh database. File `0007` requires the managed platform's `pg_cron`; the other six replay
on any stock PostgreSQL (used for the equivalence check).

