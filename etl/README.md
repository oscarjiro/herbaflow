# etl

ETL pipelines for Herbaflow — ingest, canonicalize, and load KNApSAcK Indonesia plant-compound data and external API enrichments into PostgreSQL.

---

## Module Overview

| Module             | Purpose                                                                  | Status |
| ------------------ | ------------------------------------------------------------------------ | ------ |
| `knapsack/`        | Scrape KNApSAcK World for Indonesian medicinal plant-compound pairs      | Active |
| `plants/`          | Canonicalize plant taxonomy against the GBIF Backbone                    | Active |
| `compounds/`       | Canonicalize metabolites via PubChem and ChEMBL; compute Lipinski ADME   | Active |
| `diseases/`        | Map disease queries to Disease Ontology (DO) and MeSH ontologies         | Active |
| `disease_targets/` | Fetch protein targets associated with each disease via Open Targets API  | Active |
| `load/`            | Load all pipeline CSV outputs into Supabase PostgreSQL                   | Active |

Each module has its own `README.md` with full operational and schema detail.

---

## Run Order

Run all modules end-to-end in this sequence:

```
knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/ → load/
```

Each module depends on outputs from the module(s) before it. Do not skip steps or run out of order.

```powershell
# 1. Scrape KNApSAcK
python etl/knapsack/main.py

# 2. Canonicalize plant taxonomy
python etl/plants/main.py

# 3. Canonicalize compounds (identity anchored on KNApSAcK source structures;
#    ADME computed inline during enrichment — no separate patch steps)
python etl/compounds/main.py --start 1 --end 7

# 4. Map diseases to ontologies
python etl/diseases/main.py

# 5. Fetch disease-target associations
python etl/disease_targets/main.py

# 6. Load all outputs into Supabase
python etl/load/load.py
```

---

## Module Patterns

### Scraper modules (`knapsack/`)

Single `main.py` with no numbered step directories. Fetches pages sequentially and writes output CSVs directly to `out/`. Supports `--resume` to continue an interrupted run without re-scraping already-processed plants.

### Pipeline modules (`plants/`, `compounds/`, `diseases/`, `disease_targets/`)

Multi-stage architecture with numbered step directories (`01_extract/`, `02_normalize/`, etc.), each containing a `run.py` script and its own `out/` directory. A thin `main.py` orchestrator runs all steps in sequence and supports stage range selection:

```powershell
python etl/{module}/main.py --start N --end N   # run a single stage
python etl/{module}/main.py --start N           # run from stage N to end
python etl/{module}/main.py --dry-run           # print commands without executing
```

API-calling steps cache responses to disk — subsequent runs read from cache, making reruns fast and free of redundant network calls.

---

## Shared Utilities

`etl/shared/` contains utilities used by all pipeline modules:

- `utils.py` — `ETL_ROOT`, `load_settings`, `setup_logging`, `stable_id` (UUID v5 generator), `read_csv`, `write_csv`, and other generic helpers
- `settings.yml` — cross-pipeline logging format and runtime defaults

Pipeline-specific helpers live in each module's own `utils.py`.

---

## Current Data Volume

| Entity                         | Count  |
| ------------------------------ | ------ |
| Plants (scraped)               | 535    |
| Plants (canonical)             | 519    |
| Plant-compound pairs (scraped) | 21,922 |
| Compounds (canonical)          | 11,305 |
| Compound aliases               | 73,469 |
| Plant-compound links           | 20,891 |
| Diseases (seed)                | 10     |
| Disease aliases                | 14     |
| Targets (canonical)            | 7,589  |
| Target aliases                 | 22,747 |
| Disease-target associations    | 14,736 |

---

## Setup

```powershell
# Create the venv and install all dependencies (first time only)
python -m venv etl\.venv
etl\.venv\Scripts\python.exe -m pip install -r etl/requirements.txt

# Activate before running any pipeline script
etl\.venv\Scripts\Activate.ps1
```

All ETL dependencies are declared in `etl/requirements.txt` — a single shared venv for all modules. See `etl/CLAUDE.md` for full conventions (settings schema, ID format, path resolution, utils split).
