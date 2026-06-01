# diseases

Maps a curated seed list of disease names to Disease Ontology and MeSH identifiers, producing canonical disease entities that anchor the network pharmacology scope.

---

## Purpose in the Network Pharmacology Workflow

The diseases module is the fourth stage in the Herbaflow ETL sequence:

```
knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/
```

Disease curation is the scientific framing decision for the entire network pharmacology study. The 10 canonical diseases produced here define which protein targets are retrieved from Open Targets Platform (by the downstream `disease_targets/` module), which in turn determines which compound-target overlaps can be computed. Expanding or restricting this list directly changes the scope of the analysis — selecting diseases therefore requires the same deliberateness as selecting the medicinal plant species themselves.

Ontology mapping is not purely a data-quality step; it is a prerequisite for interoperability. Open Targets Platform internally identifies diseases using Experimental Factor Ontology (EFO) identifiers, which are derived from Disease Ontology (DO) and MeSH namespaces. When `disease_targets/01_fetch/` resolves each disease to an EFO ID, it uses the standardized ontology label and DO/MeSH ID produced by this module as its search anchor. A disease that is not mapped to a recognized ontology term cannot be queried against Open Targets, and any targets it might have implicated would be silently absent from the analysis.

Disease Ontology (DO) and MeSH were chosen as the primary target vocabularies for complementary reasons. DO is the canonical OBO Foundry biomedical disease ontology, purpose-built for cross-database disease integration; it provides structured definitions, synonym hierarchies, and stable DOID identifiers used across DisGeNET, OMIM, and other resources. MeSH (Medical Subject Headings) is the U.S. National Library of Medicine's controlled vocabulary, used for PubMed indexing and embedded throughout Open Targets' literature evidence streams. Mapping to both namespaces maximizes the probability that each canonical disease can be resolved to an EFO term at query time. Ontology lookup is performed against the EBI Ontology Lookup Service (OLS4), which provides a unified REST interface to both ontologies with exact-label matching.

---

## Data Source

| Source type                 | Description                                             | URL                                     | Authentication |
| --------------------------- | ------------------------------------------------------- | --------------------------------------- | -------------- |
| Manual seed                 | Curated list of 10 target diseases (`disease_seed.csv`) | —                                       | None           |
| Disease Ontology (via OLS4) | Exact-label lookup for DOID resolution                  | `https://www.ebi.ac.uk/ols4/api/search` | None           |
| MeSH (via OLS4)             | Exact-label lookup for MeSH term resolution             | `https://www.ebi.ac.uk/ols4/api/search` | None           |

The seed list (`01_normalize/in/disease_seed.csv`) is a hand-curated set of 10 diseases representing the primary case study (Type 2 Diabetes Mellitus) and nine comparison conditions selected for their high global burden, strong target literature, and relevance to Indonesian medicinal plant research. Each seed row carries a `preferred_ontology_id` column for cases where the curator has pre-identified the correct ontology term; these manual assignments take precedence over API lookups.

Ontology lookups are cached to `02_map_ontology/out/ontology_cache.csv` after the first successful resolution. Subsequent runs load from the cache and skip the OLS4 API, ensuring reproducibility and eliminating network dependency for re-runs.

---

## Pipeline Steps

### Step 1 — `01_normalize/`

**Input:** `diseases/01_normalize/in/disease_seed.csv` (10 curated disease rows)

**What it does:**

1. Detects disease name, synonym, and reference columns by scanning a priority list of candidate column names
2. Normalizes disease names: lowercases, collapses internal whitespace, strips multi-character separators
3. Normalizes synonym fields: splits on `;`, `|`, `,`, `/`; lowercases each token; rejoins with `; `
4. Normalizes reference fields: collapses whitespace and strips trailing parenthetical annotations (e.g., `"WHO fact sheet (2023)"` → `"WHO fact sheet"`)
5. Generates `disease_name_clean` (normalized form) and `disease_key` (slug, e.g., `type_2_diabetes_mellitus`) for each row
6. Stamps provenance fields (`batch_id`, `source_name`, `source_url`) from `settings.yml` if not already present in the seed

**Output:** `01_normalize/out/disease_seed.csv`, `01_normalize/out/run_manifest.json`

**Key columns in `disease_seed.csv` (after normalization):**

| Column                   | Description                                                                |
| ------------------------ | -------------------------------------------------------------------------- |
| `seed_id`                | Original seed identifier (e.g., `D001`)                                    |
| `disease_name`           | Raw disease name from seed                                                 |
| `disease_name_clean`     | Normalized lowercase name                                                  |
| `disease_key`            | Slug key used for joining across stages (e.g., `type_2_diabetes_mellitus`) |
| `synonym_clean`          | Normalized synonym list, semicolon-delimited                               |
| `source_reference_clean` | Cleaned citation or reference string                                       |
| `batch_id`               | Batch identifier from `settings.yml` (`source.batch_id`)                   |
| `source_name`            | Source display name from `settings.yml` (`source.name`)                    |
| `source_url`             | Source URL from `settings.yml` (`source.url`)                              |

---

### Step 2 — `02_map_ontology/`

**Input:** `01_normalize/out/disease_seed.csv`

**What it does:**

1. **Tier 1 — Seed candidates:** Inspects each row for pre-supplied ontology columns (`ontology_id`, `ontology_curie`, `doid_id`, `mesh_id`, etc.). If found, uses those values directly with confidence 1.00 (unambiguous) or 0.85 (multiple conflicting candidates). Manual seed assignments always win over API lookups.
2. **Tier 2 — Cache lookup:** For rows without seed-supplied IDs, queries the local cache CSV (`ontology_cache.csv`) by `disease_key` and `query_key`. If a prior match exists, uses it (confidence preserved from original fetch).
3. **Tier 3 — Online lookup (OLS4):** For cache misses, performs an exact-label search against EBI OLS4, iterating through `preferred_sources` (Disease Ontology first, then MeSH). Tries the primary disease name first, then each synonym in order, stopping at the first successful exact match. Assigns confidence 0.90 for online exact matches.
4. Rows with no match at any tier are marked `ontology_status: unmapped` with confidence 0.0.
5. Builds a `disease_alias_map.csv` mapping all primary names and synonyms (including OLS4-returned synonyms) to disease keys for downstream search.
6. Appends newly resolved mappings to `ontology_cache.csv` for future runs.

**Output:** `02_map_ontology/out/disease_seed.csv` (enriched), `ontology_mapping.csv`, `disease_alias_map.csv`, `ontology_cache.csv`, `run_manifest.json`

**Key columns added:**

| Column                  | Description                                                      |
| ----------------------- | ---------------------------------------------------------------- |
| `ontology_id`           | Resolved identifier, underscore form (e.g., `DOID_9352`)         |
| `ontology_source`       | Source ontology name (`Disease Ontology`, `MeSH`)                |
| `ontology_label`        | Preferred label from ontology (used as canonical name in step 3) |
| `ontology_description`  | Definition text from ontology                                    |
| `ontology_synonyms`     | Semicolon-delimited synonyms returned by OLS4                    |
| `ontology_confidence`   | Float 0.0–1.0; see tier descriptions above                       |
| `ontology_status`       | `matched`, `ambiguous`, or `unmapped`                            |
| `ontology_match_method` | `seed_provided`, `cache`, or `online_exact`                      |
| `ontology_cache_hit`    | `yes` / `no`                                                     |

**Preferred source ordering:** The `ontology.preferred_sources` list in `settings.yml` controls which ontology is queried first and which candidate wins when multiple exist. Default is `[Disease Ontology, MeSH]`.

---

### Step 3 — `03_build_canonical/`

**Input:** `02_map_ontology/out/disease_seed.csv`

**What it does:**

1. Groups rows by `disease_key` and picks a representative row per group (highest ontology confidence → best status rank → label availability)
2. Chooses the canonical `disease_name`: if confidence ≥ threshold (default 0.8) and the mapping status is `matched`, `seed_provided`, `cache`, or `ambiguous`, uses the ontology label as the display name; otherwise falls back to the seed disease name
3. Generates deterministic `disease_id` via UUID v5: `uuid5(DISEASE_NS, canonical_key)`, where `canonical_key` is the ontology CURIE (`doid:{id}` preferred, then `mesh:{id}`, falling back to `disease:{slug}`) and `DISEASE_NS = uuid5(NAMESPACE_DNS, "herbaflow.diseases")` — all from `etl/shared/identity.py`
4. Builds `disease_aliases.csv` by harvesting synonyms from ontology returns, user-provided aliases in the seed, and the seed name itself; deduplicates by alias key with a priority ladder (ontology_synonym > ontology_label > user_alias > seed_name)
5. Builds `disease_alias_map.csv` as a flat search table: one row per (alias, disease_key) pair, covering primary name + all alias types
6. Writes a header-only `disease_targets_template.csv` for use by `disease_targets/`

**Output:** `03_build_canonical/out/diseases.csv`, `disease_aliases.csv`, `disease_alias_map.csv`, `disease_targets_template.csv`, `run_manifest.json`

**UUID v5 derivation:** The `disease_id` is `uuid5(DISEASE_NS, canonical_key)`, where `canonical_key` is the ontology CURIE — `doid:{id}` preferred, then `mesh:{id}`, falling back to `disease:{slug}` when no ontology id is mapped. The `disease_key` slug stays the internal join/grouping key. Identity is shared with the rest of the pipeline via `etl/shared/identity.py`, so the same key always yields the same id.

---

### Step 4 — `04_validate/`

**Input:** `03_build_canonical/out/diseases.csv`, `disease_aliases.csv`, `disease_alias_map.csv`

**What it does:**

1. Validates required columns are present in all three tables
2. Checks `disease_id` (UUID format), `disease_key` (slug format `^[a-z0-9]+(?:_[a-z0-9]+)*$`), and `alias_key` against their expected patterns
3. Checks for duplicate `disease_key` and `disease_id` values (critical)
4. Checks alias and alias-map referential integrity — all `disease_id` foreign keys must resolve to a row in `diseases.csv`
5. Checks provenance completeness: warns for blank `source_name`, `source_url`, `source_batch_id`, `retrieved_at`
6. Checks for unmapped diseases (missing `ontology_id`) — warning severity, controlled by `allow_missing_ontology_id`
7. Detects near-duplicate disease names using `difflib.SequenceMatcher` at configurable similarity threshold (`validation.near_duplicate_threshold`)
8. Raises `ValueError` and halts the pipeline if any critical issue is found and `stop_on_validation_error` is enabled

**Output:** `04_validate/out/validation_report.json`, `validation_report.csv`, `issues.csv`, `run.log`

**Severity levels:** `critical` (blocks pipeline), `warning` (logged, pipeline continues), `notice` (informational)

---

### Step 5 — `05_export/`

**Input:** `04_validate/out/validation_report.json` (status check), `03_build_canonical/out/` (source tables)

**What it does:**

1. Reads the validation report to verify `passed: true`; halts if validation failed and `export.require_validation_pass` is enabled
2. Copies `diseases.csv`, `disease_aliases.csv`, `disease_alias_map.csv`, and `disease_targets_template.csv` to `05_export/out/` applying any configured column ordering
3. Writes `run_manifest.json` with row counts, source paths, and export timestamp
4. Writes a human-readable `export_notes.txt` summary

**Output:** `05_export/out/diseases.csv`, `disease_aliases.csv`, `disease_alias_map.csv`, `disease_targets_template.csv`, `run_manifest.json`, `export_notes.txt`

The files in `05_export/out/` are the authoritative outputs consumed by `disease_targets/` and the Supabase load step.

---

## Output Schema Reference

### `diseases.csv`

One row per canonical disease. Matches the `diseases` database table. Current dataset: 10 rows.

| Column                    | Description                                                                                                        |
| ------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `disease_id`              | UUID v5 primary key — `uuid5(DISEASE_NS, canonical_key)`                                                        |
| `disease_key`             | Internal slug key (e.g., `type_2_diabetes_mellitus`); used for all joins                                           |
| `canonical_key`           | Ontology CURIE — `doid:{id}` / `mesh:{id}`, or `disease:{slug}` fallback; the uuid5 input for `disease_id`                                    |
| `disease_name`            | Display name — ontology label when confidence ≥ threshold, else seed name                                          |
| `disease_name_clean`      | Normalized lowercase display name (same as `disease_name` after normalization)                                     |
| `canonical_name_source`   | Either `ontology_label` or `seed_disease_name` — explains how `disease_name` was chosen                            |
| `seed_disease_name`       | Original name from the seed CSV (e.g., `type 2 diabetes mellitus`)                                                 |
| `seed_disease_name_clean` | Normalized seed name                                                                                               |
| `standardized_name`       | Ontology preferred label (e.g., `type 2 diabetes mellitus` from DO); used by `disease_targets/` for EFO resolution |
| `ontology_id`             | CURIE-style identifier with underscore separator (e.g., `DOID_9352`)                                               |
| `ontology_source`         | Ontology name (`Disease Ontology` or `MeSH`)                                                                       |
| `ontology_label`          | Preferred label from the matched ontology term                                                                     |
| `ontology_description`    | Definition text from the ontology                                                                                  |
| `ontology_synonyms`       | Semicolon-delimited synonyms from OLS4                                                                             |
| `confidence`              | Mapping confidence (1.00 = seed-provided, 0.90 = online exact, 0.85 = ambiguous)                                   |
| `source_id`               | Original seed row identifier (e.g., `D001`)                                                                        |
| `source_name`             | Source display name (`curated_disease_seed`)                                                                       |
| `source_url`              | Source URL (empty for manual seed)                                                                                 |
| `source_batch_id`         | Batch identifier from `settings.yml` (e.g., `D001`)                                                                |
| `retrieved_at`            | ISO 8601 UTC timestamp of ontology fetch                                                                           |
| `source_reference_clean`  | Cleaned citation from the seed (e.g., `WHO / IDF`)                                                                 |
| `ontology_status`         | `matched`, `ambiguous`, or `unmapped`                                                                              |
| `ontology_match_method`   | `seed_provided`, `cache`, or `online_exact`                                                                        |
| `ontology_query`          | The disease name string sent to OLS4                                                                               |
| `batch_id`                | Pipeline batch identifier                                                                                          |
| `created_at`              | ISO 8601 UTC timestamp of row creation                                                                             |

**Example rows:**

| disease_key                | ontology_id  | standardized_name        | confidence |
| -------------------------- | ------------ | ------------------------ | ---------- |
| `type_2_diabetes_mellitus` | `DOID_9352`  | type 2 diabetes mellitus | 0.9        |
| `hypertension`             | `DOID_10763` | hypertension             | 0.9        |
| `breast_cancer`            | `DOID_1612`  | breast cancer            | 0.9        |
| `colorectal_cancer`        | `DOID_9256`  | colorectal cancer        | 0.9        |

---

## Configuration (`settings.yml`)

| Key                                    | Default                                     | Description                                                            |
| -------------------------------------- | ------------------------------------------- | ---------------------------------------------------------------------- |
| `module.name`                          | `diseases`                                  | Module identifier used in log prefixes                                 |
| `source.name`                          | `curated_disease_seed`                      | Source display name stamped on all output rows                         |
| `source.url`                           | `""`                                        | Source URL (empty for manual seed)                                     |
| `source.batch_id`                      | `D001`                                      | Batch identifier propagated to all output records                      |
| `paths.normalize_input`                | `diseases/01_normalize/in/disease_seed.csv` | Seed file path (relative to `etl/`)                                    |
| `paths.normalize_out`                  | `diseases/01_normalize/out`                 | Step 1 output directory                                                |
| `paths.ontology_out`                   | `diseases/02_map_ontology/out`              | Step 2 output directory                                                |
| `paths.canonical_out`                  | `diseases/03_build_canonical/out`           | Step 3 output directory                                                |
| `paths.validate_out`                   | `diseases/04_validate/out`                  | Step 4 output directory                                                |
| `paths.export_out`                     | `diseases/05_export/out`                    | Step 5 output directory                                                |
| `ontology.enable_mapping`              | `true`                                      | Enable ontology mapping in step 2                                      |
| `ontology.online_lookup`               | `true`                                      | Enable OLS4 API calls (set `false` to cache-only)                      |
| `ontology.preferred_sources`           | `[Disease Ontology, MeSH]`                  | Ordered list of ontologies to query; first match wins                  |
| `ontology.request_timeout`             | `10`                                        | OLS4 HTTP request timeout in seconds                                   |
| `ontology.max_results`                 | `10`                                        | Maximum OLS4 search results to inspect per query                       |
| `validation.strict_mode`               | `true`                                      | Reserved; currently unused in validation logic                         |
| `validation.allow_missing_ontology_id` | `true`                                      | If `true`, unmapped diseases produce warnings, not failures            |
| `validation.near_duplicate_threshold`  | `0.92`                                      | `difflib.SequenceMatcher` ratio threshold for near-duplicate detection |
| `validation.fail_on`                   | `[]`                                        | Issue types to promote to critical (currently none)                    |
| `validation.warn_on`                   | `[]`                                        | Issue types to demote to warnings (currently none)                     |
| `export.format`                        | `csv`                                       | Export format                                                          |

---

## How to Run

**Prerequisites:** Activate the ETL virtual environment.

```powershell
# From repo root
etl\.venv\Scripts\Activate.ps1
```

**Full pipeline (all 5 stages):**

```powershell
python etl/diseases/main.py
```

**Single stage:**

```powershell
python etl/diseases/main.py --start 2 --end 2   # ontology mapping only
python etl/diseases/main.py --start 3 --end 5   # build → validate → export
```

**Re-run ontology lookup (clear cache to force fresh API calls):**

```powershell
# Delete the cache file — next run will re-query OLS4 for all diseases
Remove-Item etl\diseases\02_map_ontology\out\ontology_cache.csv -Force
python etl/diseases/main.py --start 2
```

To force a fresh lookup for a single disease only, open `ontology_cache.csv` and delete the row(s) for that `disease_key` before re-running step 2.

**Dry run (print commands, do not execute):**

```powershell
python etl/diseases/main.py --dry-run
```

**Unit tests:**

```powershell
etl\.venv\Scripts\python.exe -m pytest etl/tests/ -v -k diseases
```

---

## Output Interpretation

### `run_manifest.json` (from step 5)

```json
{
    "module_name": "diseases",
    "step": "05_export",
    "batch_id": "D001",
    "validation_passed": true,
    "exported_files": {
        "diseases": "...05_export/out/diseases.csv",
        "disease_aliases": "...05_export/out/disease_aliases.csv",
        "disease_alias_map": "...05_export/out/disease_alias_map.csv"
    },
    "row_counts": {
        "diseases": 10,
        "disease_aliases": 48,
        "disease_alias_map": 56
    },
    "missing_sources": [],
    "timestamp": "2026-05-06T21:56:14+00:00"
}
```

Expected values for the current 10-disease seed: `diseases: 10`, `disease_aliases: ~48`, `disease_alias_map: ~56`. `missing_sources` should be empty. If `validation_passed` is `false`, re-run step 4 and inspect `04_validate/out/issues.csv`.

### `validation_report.json` (from step 4)

```json
{
    "passed": true,
    "canonical_row_count": 10,
    "canonical_unique_disease_keys": 10,
    "canonical_unique_disease_ids": 10,
    "canonical_unmapped_count": 0,
    "critical_issue_count": 0,
    "warning_issue_count": 116,
    "issue_type_counts": { "missing_provenance_value": 116 }
}
```

`passed: true` means no critical issues. The 116 `missing_provenance_value` warnings reflect alias rows where `source_url` or `retrieved_at` are blank — expected for a manual seed with no online retrieval timestamp. All 10 diseases are mapped (`canonical_unmapped_count: 0`).

### Spot-check — verify a key disease in the output

```python
import pandas as pd

diseases = pd.read_csv("etl/diseases/05_export/out/diseases.csv")

# Type 2 Diabetes Mellitus should appear with a valid DOID
t2d = diseases[diseases["disease_key"] == "type_2_diabetes_mellitus"]
assert len(t2d) == 1, "Expected exactly one canonical row for T2DM"
assert t2d.iloc[0]["ontology_id"] == "DOID_9352", f"Unexpected DOID: {t2d.iloc[0]['ontology_id']}"
assert t2d.iloc[0]["standardized_name"] == "type 2 diabetes mellitus"
print("T2DM canonical row OK:")
print(t2d[["disease_key", "ontology_id", "standardized_name", "confidence"]].to_string(index=False))
```

Expected output:

```
T2DM canonical row OK:
        disease_key ontology_id        standardized_name  confidence
type_2_diabetes_mellitus   DOID_9352  type 2 diabetes mellitus         0.9
```

---

## Idempotency

All five stages are safe to re-run:

- **Step 1 (normalize):** Overwrites `out/` deterministically; no external calls.
- **Step 2 (map_ontology):** Reads from cache first; only calls OLS4 for cache misses. Re-running with an intact `ontology_cache.csv` makes no network requests. Delete the cache file to force fresh lookups.
- **Steps 3–5 (canonical, validate, export):** Pure computation from prior step outputs; always overwrite `out/` with identical results given identical inputs.
- **UUID v5 IDs are stable:** Re-running never changes `disease_id` values, preserving foreign key integrity in the database.
