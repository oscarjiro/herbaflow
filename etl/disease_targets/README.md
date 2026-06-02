# disease_targets ETL Pipeline

Fetches disease-target protein associations from the [Open Targets Platform](https://platform.opentargets.org/) for each canonical disease in the Herbaflow database and produces a deduplicated, normalized set of canonical targets and association records ready for PostgreSQL import.

This module is Step 4 in the Herbaflow ETL sequence:

```
knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/
```

---

## Purpose in the Network Pharmacology Workflow

Network pharmacology identifies potential mechanisms of action by overlapping:

1. **Plant compound targets** — proteins inhibited or activated by phytochemicals (from `compounds/`)
2. **Disease targets** — proteins implicated in the disease of interest (this module)

The overlap set represents candidate therapeutic targets. These candidates are then embedded into a protein–protein interaction (PPI) network, and centrality metrics identify the highest-priority targets for further validation.

This module produces the disease-target side of that overlap.

---

## Data Source: Open Targets Platform

**Open Targets** (https://platform.opentargets.org/) is a public-private partnership that systematically aggregates evidence linking human genes/proteins to diseases. It integrates data from over 30 sources including:

| Evidence type           | Examples                          |
| ----------------------- | --------------------------------- |
| Genetic associations    | GWAS Catalog, UK Biobank, ClinVar |
| Somatic mutations       | COSMIC, IntOGen                   |
| Known drugs             | ChEMBL, FDA, EMA approval data    |
| Differential expression | Expression Atlas                  |
| Animal models           | PhenoDigm (MGI mouse phenotypes)  |
| Literature mining       | EuropePMC co-occurrence           |
| Pathways                | Reactome, SIGNOR                  |

Each disease-target pair receives an **Overall Association Score** (0–1) that aggregates all evidence types. A score of 0.10 captures well-evidenced but not necessarily top-tier associations — appropriate for network pharmacology where recall is more important than precision.

**API**: GraphQL v4 at `https://api.platform.opentargets.org/api/v4/graphql`. Free, no authentication required.

---

## Pipeline Steps

### Step 1 — `01_fetch/`

**Input:** `diseases/05_export/out/diseases.csv` (10 canonical diseases)

**What it does:**

1. Loads all 10 canonical diseases (disease_name, disease_id, DOID)
2. For each disease, searches the Open Targets GraphQL API by `disease_name` to resolve the EFO (Experimental Factor Ontology) ID used internally by OT
3. Paginates the `associatedTargets` query (page size: 200) to retrieve all protein associations above the configured score threshold
4. For each target, extracts: Ensembl gene ID, approved gene symbol, approved protein name, and UniProt accession (preferring SwissProt reviewed entries over TrEMBL unreviewed)
5. Caches raw API responses as `cache/{disease_key}.json` — subsequent runs load from cache and skip the API entirely
6. Flattens all results into `raw_associations.csv`

**Output:** `01_fetch/out/raw_associations.csv`, `01_fetch/cache/`, `01_fetch/out/run_manifest.json`

**Key columns in raw_associations.csv:**

| Column              | Description                                                     |
| ------------------- | --------------------------------------------------------------- |
| `disease_key`       | Slug-normalized disease name (e.g., `type_2_diabetes_mellitus`) |
| `disease_id`        | UUID from diseases.csv                                          |
| `efo_id`            | Open Targets EFO/MONDO disease identifier                       |
| `ensembl_id`        | Ensembl gene ID (e.g., `ENSG00000105221`)                       |
| `gene_symbol`       | HGNC approved gene symbol (e.g., `AKT2`)                        |
| `approved_name`     | Full protein name                                               |
| `uniprot_accession` | UniProt accession (SwissProt preferred)                         |
| `uniprot_source`    | `uniprot_swissprot` or `uniprot_trembl`                         |
| `association_score` | Open Targets overall association score (0–1)                    |

**Caching behavior:** If `cache/{disease_key}.json` exists and `--no-cache` is not passed, the fetch step reads from disk and skips the API. Delete individual files or the entire `cache/` directory to force re-fetch. This enables fast re-runs during development.

---

### Step 2 — `02_normalize/`

**Input:** `01_fetch/out/raw_associations.csv`

**What it does:**

1. Re-applies the score threshold filter defensively (protects against cached data from a previous threshold setting)
2. Normalizes text fields: uppercases gene symbols and UniProt accessions, lowercases approved names, collapses whitespace
3. Computes `canonical_key` per target:
    - `uniprot:{accession}` if UniProt is available (99%+ of OT targets)
    - `ensembl:{id}` as fallback (pseudogenes, novel ORFs, lncRNA genes without protein IDs)
4. Deduplicates targets by `canonical_key` (sort by Ensembl ID for determinism, keep first)
5. Deduplicates disease-target pairs by `(disease_id, canonical_key)`, keeping the maximum association score where a target appears under multiple association contexts

**Output:** `02_normalize/out/targets_raw.csv`, `02_normalize/out/disease_targets_raw.csv`, `02_normalize/out/run_manifest.json`

**Why `canonical_key` uses UniProt:** Compound targets from ChEMBL (produced by `compounds/`) are also keyed by UniProt accession. Using the same convention enables direct set intersection without a cross-reference lookup step.

**UniProt coverage:** Reported in the manifest. In practice, OT returns UniProt IDs for >99% of human protein-coding gene targets.

---

### Step 3 — `03_build_canonical/`

**Input:** `02_normalize/out/targets_raw.csv`, `02_normalize/out/disease_targets_raw.csv`, `diseases/05_export/out/diseases.csv`

**What it does:**

1. Assigns deterministic UUID v5 primary keys to every target using namespace `herbaflow.targets`
2. Builds `targets.csv` with all columns matching the `targets` database table schema
3. Builds `target_aliases.csv` — three alias rows per target:
    - `ensembl_id` (Ensembl gene ID)
    - `approved_symbol` (HGNC gene symbol)
    - `approved_name` (full protein name)
4. Joins disease-target pairs with the target UUID lookup and disease UUID lookup
5. Assigns `disease_target_id` UUIDs using namespace `herbaflow.disease_targets`
6. Enforces uniqueness on `(disease_id, target_id)` — duplicates are dropped and counted

**Output:** `03_build_canonical/out/targets.csv`, `target_aliases.csv`, `disease_targets.csv`, `run_manifest.json`

**UUID generation:** All IDs are UUID v5 (deterministic). Given the same input, the same UUIDs are always produced — re-running the pipeline never changes existing IDs. This is critical for FK stability when loading incrementally into PostgreSQL.

---

### Step 4 — `04_validate/`

**Input:** `03_build_canonical/out/` (all three CSV files), `diseases/05_export/out/diseases.csv`

**Checks performed:**

| Check                                | Type | Description                                           |
| ------------------------------------ | ---- | ----------------------------------------------------- |
| `targets_required_columns`           | FAIL | All schema columns present                            |
| `target_aliases_required_columns`    | FAIL | All schema columns present                            |
| `disease_targets_required_columns`   | FAIL | All schema columns present                            |
| `targets_no_empty_pk`                | FAIL | No null/empty `target_id`                             |
| `target_aliases_no_empty_pk`         | FAIL | No null/empty `target_alias_id`                       |
| `disease_targets_no_empty_pk`        | FAIL | No null/empty `disease_target_id`                     |
| `disease_targets_no_orphan_targets`  | FAIL | All `target_id` in disease_targets exist in targets   |
| `disease_targets_no_orphan_diseases` | FAIL | All `disease_id` in disease_targets exist in diseases |
| `target_aliases_no_orphans`          | FAIL | All `target_id` in aliases exist in targets           |
| `all_diseases_covered`               | FAIL | All 10 canonical diseases have ≥1 association         |
| `disease_targets_no_dupes`           | FAIL | No duplicate `(disease_id, target_id)` pairs          |
| `score_range_valid`                  | FAIL | All scores within [threshold, 1.0]                    |
| `uniprot_coverage`                   | WARN | Coverage ≥ 60% (default; configurable)                |

FAIL checks halt the pipeline (exit code 1). WARN checks log a warning but allow continuation.

**Output:** `04_validate/out/validation_report.json`

---

### Step 5 — `05_export/`

**Input:** `03_build_canonical/out/` (validated outputs)

**What it does:** Copies the three canonical CSV files to `05_export/out/` and writes an `export_manifest.json` with row counts, source metadata, and timestamp.

**Output:** `05_export/out/targets.csv`, `target_aliases.csv`, `disease_targets.csv`, `export_manifest.json`

These are the files used for PostgreSQL import.

---

## Output Schema Reference

### `targets.csv`

Matches the `targets` database table.

| Column              | Type     | Description                                            |
| ------------------- | -------- | ------------------------------------------------------ |
| `target_id`         | UUID v5  | Primary key — deterministic from `canonical_key`       |
| `canonical_key`     | text     | `uniprot:{acc}` or `ensembl:{id}` — unique lookup key  |
| `gene_symbol`       | text     | HGNC approved gene symbol (uppercase)                  |
| `protein_name`      | text     | Full approved protein name                             |
| `uniprot_accession` | text     | UniProt ID; empty if not available                     |
| `organism_tax_id`   | text     | NCBI taxonomy ID — always `9606` (Homo sapiens)        |
| `source_id`         | text     | `OpenTargets`                                                                         |
| `source_url`        | text     | `https://platform.opentargets.org/target/{ensembl_id}`; centralized deep link via `etl/shared/provenance.py` |
| `retrieved_at`      | ISO 8601 | UTC timestamp of fetch                                 |

### `target_aliases.csv`

Matches the `target_aliases` database table.

| Column            | Type     | Description                                        |
| ----------------- | -------- | -------------------------------------------------- |
| `target_alias_id` | UUID v5  | Deterministic from `(target_id, alias_name)`       |
| `target_id`       | UUID v5  | FK → targets                                       |
| `alias_name`      | text     | The alias value                                    |
| `alias_key`       | text     | Lowercased slug of alias_name                      |
| `alias_type`      | text     | `ensembl_id` / `approved_symbol` / `approved_name` |
| `source_id`       | text     | `OpenTargets`                                                                    |
| `source_url`      | text     | Target page URL; centralized deep link via `etl/shared/provenance.py`            |
| `retrieved_at`    | ISO 8601 | UTC timestamp                                      |

### `disease_targets.csv`

Matches the `disease_targets` database table.

| Column              | Type     | Description                                      |
| ------------------- | -------- | ------------------------------------------------ |
| `disease_target_id` | UUID v5  | Deterministic from `(disease_id, target_id)`                                        |
| `disease_id`        | UUID v5  | FK → diseases                                                                        |
| `target_id`         | UUID v5  | FK → targets                                                                         |
| `source_id`         | text     | `OpenTargets`                                                                        |
| `source_url`        | text     | Per-row Open Targets disease-target page; centralized deep link via `etl/shared/provenance.py` |
| `association_type`  | text     | `open_targets_overall`                                                               |
| `score`             | float    | Open Targets overall association score (0.1–1.0)                                     |
| `retrieved_at`      | ISO 8601 | UTC timestamp                                                                        |

Unique constraint enforced: `(disease_id, target_id)`.

---

## Configuration (`settings.yml`)

| Key                                         | Default                               | Description                                       |
| ------------------------------------------- | ------------------------------------- | ------------------------------------------------- |
| `source.batch_id`                           | `DT001`                               | Batch identifier propagated to all output records |
| `paths.diseases_input`                      | `diseases/05_export/out/diseases.csv` | Upstream input                                    |
| `api.page_size`                             | `200`                                 | Targets per GraphQL page (OT max: 500)            |
| `api.max_pages`                             | `100`                                 | Safety cap on pagination                          |
| `api.timeout_seconds`                       | `30`                                  | Per-request timeout                               |
| `api.retry_attempts`                        | `3`                                   | Retries on network error                          |
| `api.retry_delay_seconds`                   | `2`                                   | Base delay (multiplied by attempt number)         |
| `filtering.min_association_score`           | `0.10`                                | Minimum overall score to include                  |
| `filtering.organism_tax_id`                 | `9606`                                | Written to targets.csv; OT is human-only          |
| `filtering.require_uniprot`                 | `false`                               | If `true`, drop targets with no UniProt ID        |
| `filtering.uniprot_coverage_warn_threshold` | `0.60`                                | Warn if UniProt coverage below this               |
| `validation.fail_on`                        | `[]`                                  | Checks to promote from WARN to FAIL               |
| `validation.warn_on`                        | `[low_uniprot_coverage]`              | Checks that produce warnings, not failures        |

---

## How to Run

**Prerequisites:** Activate the ETL virtual environment first.

```powershell
# From repo root
etl\.venv\Scripts\Activate.ps1
```

**Full pipeline:**

```powershell
python etl/disease_targets/main.py
```

**Single stage:**

```powershell
python etl/disease_targets/main.py --start 2 --end 2   # normalize only
python etl/disease_targets/main.py --start 3 --end 5   # build → validate → export
```

**Re-fetch ignoring cache:**

```powershell
python etl/disease_targets/01_fetch/run.py --no-cache
```

**Dry run (print config, do not execute):**

```powershell
python etl/disease_targets/01_fetch/run.py --dry-run
```

**Unit tests:**

```powershell
python -m pytest etl/tests/test_disease_targets_utils.py -v
```

---

## Output Interpretation

### `export_manifest.json`

```json
{
    "batch_id": "DT001",
    "source": "OpenTargets",
    "targets": 7589,
    "target_aliases": 22767,
    "disease_targets": 14736,
    "diseases_covered": 10,
    "exported_at": "2026-05-16T11:07:30+00:00"
}
```

Expected ranges for 10 diseases at score ≥ 0.10:

- **targets**: 5,000–10,000 (depends on disease set and OT version)
- **disease_targets**: 10,000–20,000 (many targets shared across diseases)
- **diseases_covered**: must equal 10

### `validation_report.json`

All checks appear as `PASS`, `WARN`, or `FAIL`. The `uniprot_coverage` check includes the actual percentage:

```json
{
    "check": "uniprot_coverage",
    "status": "PASS",
    "detail": "99.1% (threshold: 60%)",
    "uniprot_coverage": 0.991
}
```

A result below 60% is unusual and indicates OT may have returned many non-protein-coding genes (lncRNAs, pseudogenes) — review the disease list and consider increasing the score threshold.

### Spot-checking known targets

After a successful run, verify biologically expected associations:

```python
import pandas as pd
dt = pd.read_csv("etl/disease_targets/05_export/out/disease_targets.csv")
tgt = pd.read_csv("etl/disease_targets/05_export/out/targets.csv")

# Type 2 diabetes should include insulin receptor and PPARG
t2d_disease_id = "<disease_id from diseases.csv>"
t2d_targets = dt[dt["disease_id"] == t2d_disease_id].merge(tgt, on="target_id")
print(t2d_targets[["gene_symbol", "score"]].sort_values("score", ascending=False).head(20))
# Expected in top results: INSR, PPARG, GCK, HNF1A, SLC2A2
```

---

## Idempotency

The pipeline is safe to re-run:

- **01_fetch** reads from cache by default — no redundant API calls
- **02–05** overwrite `out/` files deterministically — same input always produces identical output
- UUID v5 IDs are stable — re-running does not change existing primary keys

To force a complete re-fetch (e.g., after 6 months to capture updated OT data):

```powershell
Remove-Item etl\disease_targets\01_fetch\cache\* -Force
python etl/disease_targets/main.py
```
