# ETL Pipelines

Five sequential modules that canonicalize Indonesian medicinal plant data sourced from KNApSAcK.

## Pipeline Order

```
knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/
```

## Modules

| Module | Stages | Purpose | Key Outputs |
|---|---|---|---|
| `knapsack/` | 1 | Scrape KNApSAcK Indonesia | plants.csv, plants_compounds.csv |
| `plants/` | 7 | Canonicalize plant taxonomy via GBIF | plants.csv, plant_aliases.csv |
| `compounds/` | 7 | Canonicalize metabolites: identity anchored on KNApSAcK source structures (formula-corroborated), PubChem/ChEMBL fallback; ADME computed inline | compounds.csv, plant_compounds.csv |
| `diseases/` | 5 | Map diseases to DO/MeSH ontologies | diseases.csv, disease_aliases.csv |
| `disease_targets/` | 5 | Fetch protein targets via Open Targets API | targets.csv, target_aliases.csv, disease_targets.csv |

## Folder Structure

```
etl/
├── shared/
│   ├── settings.yml    # Cross-pipeline logging and runtime defaults
│   └── utils.py        # ETL_ROOT, load_settings, shared helpers
├── knapsack/           # Scraper — single main.py
├── plants/             # 7-stage plant taxonomy pipeline
├── compounds/          # 7-stage compound canonicalization pipeline
├── diseases/           # 5-stage disease ontology pipeline
├── disease_targets/    # 5-stage target association pipeline (Open Targets API)
├── load/
│   └── load.py         # CSV → Supabase loader (run after all pipelines)
└── tests/              # Unit tests for shared and pipeline utils
```

## Module Conventions

Each module follows this structure:
- `README.md` — module documentation (required; create with the `etl-module-readme` skill)
- `CLAUDE.md` — non-obvious conventions for AI sessions (required)
- `settings.yml` — paths, thresholds, API settings (all paths relative to `etl/`)
- `utils.py` — entity-specific helpers
- `main.py` — thin orchestrator with `--start`/`--end` range selection
- `NN_step_name/run.py` — numbered step script
- `NN_step_name/out/` — step outputs (CSV, logs, manifests)

## Python Environment

**Always use the ETL venv.** Activate before running any script:

```powershell
# From repo root
etl\.venv\Scripts\Activate.ps1

# Then run as normal
python etl/{module}/main.py
```

Or invoke the venv Python directly without activating:

```powershell
etl\.venv\Scripts\python.exe etl/{module}/main.py
```

Never use the system Python for ETL work — package versions will differ.

Run a module: `python etl/{module}/main.py` (with venv active).
Run a single stage: `python etl/{module}/main.py --start 3 --end 3`

## Naming Conventions

- All Python files: `snake_case`
- Stage directories: `NN_step_name/` (number-prefixed for ordering)
- Step scripts: `run.py` (one per stage). Exception: `04_build_canonical/` in plants uses `run_part1.py` + `run_part2.py` (two substeps) plus `resolve_manual_reviews.py`, an ordered stage that runs between them

## Settings Schema

Every `settings.yml` follows this top-level structure:

```yaml
module:
  name: <module_name>

source:
  name: <display_name>
  url: <source_url>
  batch_id: <id_or_auto>

paths:
  # All paths relative to etl/ root

validation:
  fail_on: [...]
  warn_on: [...]

export:
  format: csv

# Module-specific sections (gbif:, enrichment:, ontology:, etc.)
```

Cross-pipeline defaults (logging format, runtime flags) live in `shared/settings.yml`.

## ID Conventions

All entity IDs use **UUID v5** (deterministic, no prefix):

| Entity | Field | Namespace constant | Input key |
|---|---|---|---|
| Plant | `plant_id` | `PLANT_NS` in `plants/utils.py` | GBIF usage key |
| Compound | `compound_id` | `COMPOUND_NS` in `compounds/utils.py` | InChIKey or canonical key |
| Disease | `disease_id` | `DISEASE_NS` in `diseases/utils.py` | Ontology ID (DOID/MeSH) |
| Target | `target_id` | `TARGET_NS` in `disease_targets/utils.py` | `uniprot:{acc}` or `ensembl:{id}` |

Generated via `stable_id(NAMESPACE, key)` from `shared/utils.py`.

IDs are deterministic: same input always produces the same UUID. No prefixes — the column name (`plant_id`, `compound_id`) provides type context in the database schema.

## Shared vs Pipeline-Level Utils

**`shared/utils.py`** — generic stdlib helpers (`list[dict]` CSV I/O), used by all pipelines:
`ETL_ROOT`, `load_settings`, `setup_logging`, `ensure_dir`, `now_iso`, `make_run_id`, `read_csv`, `write_csv`, `write_json`, `normalize_whitespace`, `normalize_unicode`, `to_key`, `safe_str`, `clean_str`, `normalize_text`, `stable_id`

**`shared/frames.py`** — pandas DataFrame I/O for the pandas-native modules (`diseases`, `disease_targets`):
`read_frame`, `write_frame`, `validate_required_columns`. Kept separate from `shared/utils.py` so the stdlib (`list[dict]`) and pandas (`DataFrame`) I/O idioms never collide under one name.

**`shared/identity.py`** — single source of truth for every canonical key and UUID (`slugify`, the `*_canonical_key`/`*_id` builders, namespace constants). Stdlib-only; module helpers never pre-normalize an identity input.

**Text helpers — two honest names:** `safe_str` strips only (used by `plants`, `compounds`); `clean_str` strips **and** folds missing-markers (`na`/`none`/`-`/`unknown`/… → `""`) — used by `diseases`, `disease_targets`. `normalize_text` = lowercase + collapse whitespace + fold.

**Pipeline `utils.py`** — entity-specific only (e.g. `canonical_key_for_target`). If a function is generic, it belongs in shared. The `diseases` and `disease_targets` `utils.py` are thin re-export facades over the shared modules.

## Path Resolution

All scripts resolve paths using `ETL_ROOT` from `shared/utils.py`:

```python
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[N]))  # N=1 for module root, N=2 for step scripts
from shared.utils import ETL_ROOT, load_settings

cfg = load_settings("plants")
input_path = ETL_ROOT / cfg["paths"]["extract"]["input"]
```

No script uses CWD-relative paths or hardcoded absolute paths.

## Shared Patterns

- Every record tracks: `source_name`, `source_url`, `source_batch_id`, `retrieved_at`
- Uncertain matches go to a review CSV for manual decision before the next stage proceeds
- API responses are cached (TTL in each module's settings.yml) — delete the module's cache dir to re-fetch
- All scripts are idempotent: safe to rerun with the same outputs
- Validation rules (fail/warn criteria) are declared in each module's `settings.yml`

## Do Not Touch

- `out/` directories — written by pipeline scripts only (exception: `plants/04_build_canonical/out/manual_review_decisions.csv` is a curator-authored input, read by the resolve stage)
- `.venv/` under `etl/`

## Python Dependencies

All ETL dependencies are declared in `etl/requirements.txt` — a single file for the entire venv, kept in sync via pip freeze.

**After installing any new package:**

```powershell
etl\.venv\Scripts\python.exe -m pip freeze > etl/requirements.txt
```

Commit the updated `requirements.txt` alongside the code change. Never add per-module `requirements.txt` files — everything runs in the shared venv.

**Restore the venv from scratch:**

```powershell
python -m venv etl\.venv
etl\.venv\Scripts\python.exe -m pip install -r etl/requirements.txt
```

## Running Tests

```powershell
etl\.venv\Scripts\python.exe -m pytest etl/tests/ -v
```
