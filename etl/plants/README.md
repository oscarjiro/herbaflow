# plants

Receives raw plant names from the KNApSAcK scrape output and produces canonical plant entities matched to GBIF taxonomy, ready for PostgreSQL import.

This module is Step 2 in the Herbaflow ETL sequence:

```
knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/
```

---

## Purpose in the Network Pharmacology Workflow

Taxonomic canonicalization is a prerequisite for any cross-database network pharmacology analysis. KNApSAcK records plant species using a mix of accepted names, synonyms, and vernacular spellings scraped from web pages. Without resolving these to a single authoritative accepted name per taxon, the same biological species may appear under multiple keys, causing fragmentation of compound–plant linkage tables and inflating apparent species diversity.

The Global Biodiversity Information Facility (GBIF) Backbone Taxonomy is used as the canonical reference because it is the most comprehensive global checklist for vascular plants, integrating sources including Catalogue of Life, IPNI, and The Plant List. GBIF provides both accepted names and synonym resolution: given any synonym or outdated name, the API returns the accepted usage and its `usageKey` — a stable integer identifier for the accepted taxon. This key is used as the basis for all downstream primary keys in the Herbaflow database.

The `gbif_usage_key` (equivalently, `gbif_accepted_usage_key` for synonyms) enables unambiguous plant–compound linkage in the `compounds/` module: when KNApSAcK records a compound–plant pair, both the plant canonical key (`gbif:{usageKey}`) and the compound canonical key (PubChem CID or InChIKey) reference stable, authority-backed identifiers. This means the plant–compound association table can be joined correctly across pipeline runs without manual reconciliation of spelling variants.

---

## Data Source

**Upstream:** KNApSAcK raw plant names from `knapsack/out/plants.csv`.

**Taxonomy API:** GBIF Species Match API.

| Source | URL | Evidence type | Auth required | Rate limits |
|---|---|---|---|---|
| KNApSAcK World | https://www.knapsackfamily.com | Indonesian medicinal plant–compound associations (scraped) | None | N/A (local file) |
| GBIF Species Match API | https://api.gbif.org/v2/species/match | Taxonomic name matching against GBIF Backbone | None | Polite use; `User-Agent` header required |
| GBIF Species Lookup API | https://api.gbif.org/v1/species/{key} | Full taxon metadata for manual review resolution | None | Polite use |

---

## Pipeline Steps

### Step 1 — `01_extract/`

**Input:** `knapsack/out/plants.csv` (raw scrape output)

**What it does:**

1. Reads raw rows from the KNApSAcK scrape; preserves all columns unchanged
2. Trims outer whitespace on all field values (no semantic normalization)
3. Fills or adds `source_batch_id` from settings (`source.batch_id`)
4. Drops rows where `detail_url` is missing (unfetchable scrape artifacts)
5. Computes `raw_hash` as a SHA-256 fingerprint of all column values for each row
6. Removes exact duplicate rows (same hash)
7. Writes a human-readable extraction summary log alongside the output

**Output:** `01_extract/out/stg_plants.csv`, `01_extract/out/extract_plants.log`

**Key columns in stg_plants.csv:**

| Column | Description |
|---|---|
| `species_name` | Raw scraped plant name string |
| `family_name` | Scraped family name (may be empty) |
| `common_name` | Scraped common/vernacular name |
| `detail_url` | Source URL on KNApSAcK (used as `source_url` downstream) |
| `source_batch_id` | Batch identifier (from settings `source.batch_id`) |
| `raw_hash` | SHA-256 of all row values — used for deduplication |

---

### Step 2 — `02_normalize_taxonomy/`

**Input:** `01_extract/out/stg_plants.csv`

**What it does:**

1. Preserves the original scraped name in `original_species_name`
2. Applies NFKC Unicode normalization and collapses whitespace runs
3. Normalizes common punctuation spacing (parentheses, commas, semicolons)
4. Splits each scientific name string into three components using heuristic token analysis:
   - `verbatim_scientific_name` — the lightly normalized full string
   - `canonical_candidate_name` — genus + epithet (+ infraspecific rank tokens if present)
   - `authorship_candidate` — remaining tokens identified as authorship text
5. Builds `canonical_lookup_key` from the canonical candidate: lowercased, accent-stripped, punctuation-removed
6. Drops rows where the species name is entirely empty after normalization
7. Writes a normalization report with counts

**Output:** `02_normalize_taxonomy/out/normalized_plants.csv`, `02_normalize_taxonomy/out/normalize_taxonomy_report.txt`

**Key columns in normalized_plants.csv:**

| Column | Description |
|---|---|
| `original_species_name` | Raw scraped string (preserved verbatim) |
| `verbatim_scientific_name` | Lightly normalized full string |
| `canonical_candidate_name` | Heuristic genus+epithet extraction (pre-GBIF) |
| `authorship_candidate` | Heuristic authorship tokens |
| `canonical_lookup_key` | Normalized lowercase key used for GBIF deduplication |

---

### Step 3 — `03_match_gbif/`

**Input:** `02_normalize_taxonomy/out/normalized_plants.csv`

**What it does:**

1. Builds a deduplicated query table by grouping rows on `canonical_lookup_key` — each unique lookup key produces one GBIF API call regardless of how many source rows share it
2. For each unique query, computes a deterministic SHA-256 cache key from the query payload
3. Checks `cache/` directory for a matching JSON file; if found, uses the cached response without calling the API
4. For cache misses, calls the GBIF Species Match API (`/v2/species/match?scientificName=...`) with configurable timeout and exponential backoff retry logic
5. Caches both successful and failed responses (failures are also cached to prevent repeated retries on persistent errors)
6. Flattens each JSON response into a tabular row with all GBIF taxonomy fields
7. Writes a single output CSV joining every input row to its GBIF match result

**Caching behavior:** Each unique query is cached as `cache/{sha256}.json`. On re-run, cached entries are loaded and no API call is made. To force re-fetch for all or specific species, delete the corresponding files from the `cache/` directory. The cache has no TTL enforcement at read time — cache entries are permanent until deleted.

**Output:** `03_match_gbif/out/gbif_matches.csv`, `03_match_gbif/out/cache/`

**Key columns in gbif_matches.csv:**

| Column | Description |
|---|---|
| `input_name` | The name string sent to the GBIF API |
| `canonical_lookup_key` | Deduplication key |
| `source_row_count` | Number of input rows sharing this query |
| `query_status` | `ok` or `error` |
| `matched_name` | GBIF matched name (may be a synonym) |
| `accepted_name` | GBIF accepted name for this taxon |
| `match_type` | `EXACT`, `VARIANT`, `FUZZY`, `HIGHERRANK`, etc. |
| `confidence` | GBIF match confidence score (0–100) |
| `gbif_usage_key` | GBIF usage key for the matched name |
| `gbif_accepted_usage_key` | GBIF usage key for the accepted name (preferred ID) |
| `gbif_species_key` | Species-rank GBIF key |
| `gbif_genus_key` | Genus-rank GBIF key |
| `gbif_family_key` | Family-rank GBIF key |
| `gbif_kingdom_key` | Kingdom-rank GBIF key |
| `cache_key` | SHA-256 of the query payload |
| `cache_path` | Absolute path to the cached JSON file |

---

### Step 4 — `04_build_canonical/`

This step has three scripts: `run_part1.py` (automated classification), `run_part2.py` (canonical entity assembly), and `resolve_manual_reviews.py` (operator tool for manual decisions).

#### Part 1 — `run_part1.py`

**Input:** `03_match_gbif/out/gbif_matches.csv`

**What it does:**

1. Applies deterministic acceptance rules to classify each GBIF match row:
   - **accepted**: `match_type` in `{EXACT, VARIANT}` and `confidence ≥ 90` and `taxonomic_status` in `{ACCEPTED, SYNONYM}`
   - **review**: plausible match (confidence ≥ 70, or HIGHERRANK with confidence ≥ 80) that does not meet full acceptance criteria
   - **rejected**: failed query, missing match, or confidence below all thresholds
2. Normalizes GBIF identifier fields (removes float-like suffixes from integer IDs)
3. Populates `canonical_scientific_name` from GBIF `accepted_name` (preferred) or `matched_name`
4. Adds `decision` and `decision_reason` columns to all rows
5. Writes accepted, review, and rejected rows to separate CSVs
6. Writes an empty `manually_accepted_review_plants.csv` as a stub for operator decisions
7. Writes a classification report with counts and threshold documentation

**Output:** `04_build_canonical/out/accepted_plants.csv`, `review_plants.csv`, `rejected_plants.csv`, `manually_accepted_review_plants.csv`, `build_canonical_report.txt`

#### Manual review step — `resolve_manual_reviews.py`

This is an **operator tool**, not part of the automated pipeline. Run it after reviewing `review_plants.csv` and populating `manual_review_decisions.csv`.

`manual_review_decisions.csv` must have columns: `input_name`, `gbif_id` (the correct GBIF usageKey), `raw_plant_id`.

For each row, the script:

1. Calls the GBIF Species API (`/v1/species/{key}`) to fetch full taxon metadata for the manually verified usageKey
2. Resolves synonyms to their accepted usage
3. Builds a complete "big shape" row compatible with `accepted_plants.csv` format
4. Writes results to `manually_accepted_review_plants.csv`

**Output:** `04_build_canonical/out/manually_accepted_review_plants.csv`

#### Part 2 — `run_part2.py`

**Input:** `04_build_canonical/out/accepted_plants.csv` + `manually_accepted_review_plants.csv`

**What it does:**

1. Merges automatically accepted rows with manually accepted review rows
2. Groups rows by a computed `canonical_key` (derived from accepted name + authorship) — one group becomes one canonical plant entity
3. Picks a representative row per group (highest GBIF confidence, then lexicographic sort for determinism)
4. Generates a deterministic `plant_id` (UUID v5) from the GBIF usage key via `PLANT_NS` namespace
5. Computes `canonical_key` as `{folded_name}|{folded_authorship}` (pipe-separated, accent-folded lowercase)
6. Builds alias rows for each source row variant:
   - `exact_scraped_spelling` — the original scraped name
   - `normalized_variant` — canonical candidate or accepted name when different from scraped spelling
   - `author_variant` — canonical candidate + authorship candidate string
   - `synonym_variant` — GBIF matched name when it differs from accepted name
7. Deduplicates aliases by `(alias_key, alias_type)` within each plant group
8. Writes `plants.csv` and `plant_aliases.csv` with stable sort for deterministic output
9. Writes a report listing any input rows merged into shared canonical groups

**Output:** `04_build_canonical/out/plants.csv`, `plant_aliases.csv`, `build_canonical_part2_report.txt`

---

### Step 5 — `05_validate/`

**Input:** `04_build_canonical/out/plants.csv`, `04_build_canonical/out/plant_aliases.csv`

**What it does:**

1. Checks that all required schema columns are present in both files (FAIL if missing)
2. Checks for duplicate `plant_id` and `canonical_key` values (FAIL)
3. Checks for duplicate `alias_id` and logical key `(plant_id, alias_key, alias_type)` (FAIL)
4. Checks for orphan aliases — alias rows whose `plant_id` is not in `plants.csv` (FAIL)
5. Checks for empty `canonical_scientific_name` values (FAIL)
6. Checks for suspicious canonical names: fewer than 2 tokens, digits present, unusual punctuation (WARN)
7. Checks that `source_name` contains a source system name, not a plant name (FAIL)
8. Checks that authorship is not embedded inside `canonical_scientific_name` (FAIL)
9. Checks that GBIF identifier columns do not contain float-like strings (FAIL)
10. Writes validated pass-through CSVs when no structural failures are found
11. Writes `validation_report.csv` (row-level issues) and `validation_report.json` (summary)

FAIL checks cause exit code 1 and halt the pipeline. WARN checks log a warning but allow continuation.

**Output:** `05_validate/out/plants.csv`, `plant_aliases.csv`, `validation_report.csv`, `validation_report.json`

---

### Step 6 — `06_export/`

**Input:** `05_validate/out/plants.csv`, `05_validate/out/plant_aliases.csv`

**What it does:**

1. Reads validated outputs and enforces exact schema column order
2. Normalizes all identifier fields one final time (removes float-like suffixes)
3. Sorts both files deterministically (`plants.csv` by `canonical_key, plant_id`; `plant_aliases.csv` by `plant_id, alias_type, alias_key, alias_id`)
4. Writes final `plants.csv` and `plant_aliases.csv` to `06_export/out/`
5. Optionally writes SQL INSERT files for `plants` and `plant_aliases` tables (`--emit-sql`)
6. Writes `export_manifest.json` with row counts, source paths, schema column lists, and timestamp

**Output:** `06_export/out/plants.csv`, `plant_aliases.csv`, `export_manifest.json`

---

## Output Schema Reference

### `plants.csv`

These are the files used for PostgreSQL import into the `plants` table.

| Column | Type | Description |
|---|---|---|
| `plant_id` | UUID v5 | Primary key — deterministic UUID v5 generated from `PLANT_NS` namespace and `gbif_usage_key` |
| `raw_plant_id` | text | Sequential integer ID from the original KNApSAcK scrape row |
| `canonical_key` | text | `{folded_name}\|{folded_authorship}` — pipe-separated, lowercased, accent-folded; unique lookup key |
| `canonical_scientific_name` | text | GBIF-resolved accepted scientific name (without authorship) |
| `authorship` | text | Botanical authorship string (stored separately from the name) |
| `family_name` | text | Family name (from GBIF or scraped; may be empty) |
| `taxonomic_status` | text | `ACCEPTED` or `SYNONYM` (uppercased from GBIF) |
| `rank` | text | Taxonomic rank: `SPECIES`, `SUBSPECIES`, `VARIETY`, etc. |
| `gbif_usage_key` | text | GBIF integer key for the matched name (may be a synonym key) |
| `gbif_accepted_usage_key` | text | GBIF integer key for the accepted taxon (preferred for cross-linking) |
| `gbif_species_key` | text | Species-rank GBIF key from GBIF classification |
| `gbif_genus_key` | text | Genus-rank GBIF key |
| `gbif_family_key` | text | Family-rank GBIF key |
| `gbif_kingdom_key` | text | Kingdom-rank GBIF key |
| `source_name` | text | Source system name: `KNApSAcK World` |
| `source_url` | text | KNApSAcK detail page URL for this plant (from scrape) |
| `source_batch_id` | text | Batch identifier from settings (`source.batch_id`) |
| `retrieved_at` | ISO 8601 | UTC timestamp when the scrape row was retrieved |
| `confidence` | text | GBIF match confidence score (0–100); `100` for manual overrides |

### `plant_aliases.csv`

Matches the `plant_aliases` database table. Each plant has one or more alias rows covering all name variants seen in the source data.

| Column | Type | Description |
|---|---|---|
| `alias_id` | UUID v5 | Deterministic from `PLANT_ALIAS_NS`, `plant_id`, `alias_type`, `alias_name` |
| `plant_id` | UUID v5 | FK → plants |
| `alias_name` | text | The alias string (e.g. original scraped spelling, matched name) |
| `alias_key` | text | Lowercased, accent-folded, punctuation-stripped form of `alias_name` |
| `alias_type` | text | One of: `exact_scraped_spelling`, `normalized_variant`, `author_variant`, `synonym_variant` |
| `source_name` | text | Source system name for this alias row |
| `source_url` | text | KNApSAcK detail page URL |
| `source_batch_id` | text | Batch identifier |
| `retrieved_at` | ISO 8601 | UTC timestamp |

---

## Configuration (`settings.yml`)

| Key | Default | Description |
|---|---|---|
| `source.name` | `KNApSAcK World` | Source system display name propagated to all output records |
| `source.url` | `https://www.knapsackfamily.com` | Source base URL |
| `source.batch_id` | `knapsack_world_id_2026_04_17` | Batch identifier written to `source_batch_id` in all outputs |
| `paths.extract.input` | `knapsack/out/plants.csv` | Raw KNApSAcK scrape input |
| `paths.match_gbif.cache_dir` | `plants/03_match_gbif/out/cache` | GBIF response cache directory |
| `gbif.base_url` | `https://api.gbif.org/v2` | GBIF API base URL |
| `gbif.match_endpoint` | `/species/match` | GBIF species match endpoint path |
| `gbif.user_agent` | `indonesian-medicinal-plants-etl/1.0` | HTTP `User-Agent` sent with all GBIF requests |
| `gbif.cache_responses` | `true` | Enable local JSON caching of API responses |
| `gbif.cache_ttl_days` | `3650` | Nominal cache TTL (not enforced at read time; delete files to invalidate) |
| `gbif.api.timeout_seconds` | `30` | Per-request HTTP timeout |
| `gbif.api.max_retries` | `5` | Maximum retry attempts for transient errors (429, 5xx) |
| `gbif.api.backoff_base_seconds` | `1.5` | Exponential backoff base delay |
| `gbif.api.backoff_max_seconds` | `60.0` | Maximum backoff cap |
| `gbif.accept_rules.accept_min_confidence` | `90` | Minimum GBIF confidence for automatic acceptance |
| `gbif.accept_rules.review_min_confidence` | `70` | Minimum confidence for routing to manual review |
| `gbif.accept_rules.higherrank_review_min_confidence` | `80` | Minimum confidence for higher-rank matches routed to review |
| `gbif.accept_rules.reject_below_confidence` | `70` | Rows with confidence below this are rejected outright |
| `validation.fail_on` | (list) | Check names that cause exit code 1 on failure |
| `validation.warn_on` | (list) | Check names that produce warnings without halting |
| `export.format` | `csv` | Export format; `sql` requires `--emit-sql` flag |

---

## How to Run

**Prerequisites:** Activate the ETL virtual environment first.

```powershell
# From repo root
etl\.venv\Scripts\Activate.ps1
```

**Full pipeline (all 6 stages):**

```powershell
python etl/plants/main.py
```

**Single stage:**

```powershell
python etl/plants/main.py --start 3 --end 3   # GBIF matching only
python etl/plants/main.py --start 4 --end 5   # build canonical → validate
python etl/plants/main.py --start 5 --end 6   # validate → export
```

**Dry run (prints commands, does not execute):**

```powershell
python etl/plants/main.py --dry-run
```

**Manual review workflow (after running stage 4 part 1):**

```powershell
# 1. Review etl/plants/04_build_canonical/out/review_plants.csv
# 2. Create manual_review_decisions.csv with columns: input_name, gbif_id, raw_plant_id
# 3. Run the resolution tool:
python etl/plants/04_build_canonical/resolve_manual_reviews.py
# 4. Resume from part 2:
python etl/plants/main.py --start 4 --end 4
```

Note: `--start 4` runs both part 1 and part 2. To run only part 2 (after manual review), run `run_part2.py` directly:

```powershell
python etl/plants/04_build_canonical/run_part2.py
```

**Bypass GBIF cache (force re-fetch):**

```powershell
# Delete all cached responses
Remove-Item etl\plants\03_match_gbif\out\cache\* -Force

# Then re-run from stage 3
python etl/plants/main.py --start 3
```

To delete only specific species cache entries, remove the individual `{sha256}.json` files from the cache directory.

**Export with SQL:**

```powershell
python etl/plants/06_export/run.py --emit-sql
```

**Tests:**

```powershell
python -m pytest etl/tests/ -v -k plants
```

---

## Output Interpretation

### `export_manifest.json`

```json
{
  "dry_run": false,
  "emit_sql": false,
  "generated_at": "2026-04-22T23:13:16.993027+00:00",
  "input_dir": "05_validate\\out",
  "outputs": {
    "plant_aliases_csv": "06_export\\out\\plant_aliases.csv",
    "plants_csv": "06_export\\out\\plants.csv"
  },
  "row_counts": {
    "aliases_input_rows": 597,
    "aliases_output_rows": 597,
    "plants_input_rows": 519,
    "plants_output_rows": 519
  },
  "schema": {
    "plant_aliases_columns": ["alias_id", "plant_id", "..."],
    "plants_columns": ["plant_id", "raw_plant_id", "..."]
  },
  "status": "written"
}
```

Expected ranges for a full KNApSAcK Indonesia scrape:
- **plants**: 400–600 (depends on GBIF match acceptance rate; ~519 in current run)
- **plant_aliases**: 2–4 aliases per plant on average (~597 in current run)

### `validation_report.json`

```json
{
  "generated_at": "2026-04-22T23:13:16.257470+00:00",
  "summary": {
    "aliases_rows": 597,
    "critical_issues": 0,
    "plants_rows": 519,
    "status": "pass",
    "total_issues": 7,
    "warning_issues": 7
  },
  "checks": {
    "suspicious_canonical_name": {
      "critical": 0,
      "total": 7,
      "warning": 7
    }
  }
}
```

`status: "pass"` means no critical issues. A `suspicious_canonical_name` warning is expected for single-word genera or species names that passed GBIF review at a higher rank (e.g. genus-only matches). Review the `validation_report.csv` to inspect individual flagged rows.

A `status: "fail"` result halts the pipeline with exit code 1 and must be resolved before proceeding to export.

### Spot-checking a known species

After a successful run, verify that a well-known Indonesian medicinal plant appears correctly:

```python
import pandas as pd

plants = pd.read_csv("etl/plants/06_export/out/plants.csv")
curcuma = plants[plants["canonical_scientific_name"].str.startswith("Curcuma longa")]
print(curcuma[["plant_id", "canonical_scientific_name", "gbif_accepted_usage_key", "confidence"]])

# Expected: Curcuma longa L. with gbif_accepted_usage_key = 2757881 (or similar valid GBIF key)
# confidence should be 97–100 for an EXACT match
```

---

## Idempotency

The pipeline is safe to re-run:

- **01_extract–04_build_canonical** overwrite `out/` files deterministically — same input always produces identical output
- **03_match_gbif** reads from the local JSON cache by default — no redundant API calls on re-run
- **UUID v5 IDs are stable** — `plant_id` and `alias_id` are derived from fixed inputs; re-running the pipeline never changes existing primary keys. This is critical for FK stability when loading incrementally into PostgreSQL

To force a complete re-fetch from GBIF (e.g., after the GBIF Backbone is updated):

```powershell
Remove-Item etl\plants\03_match_gbif\out\cache\* -Force
python etl/plants/main.py
```
