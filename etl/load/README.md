# load

Reads final CSV outputs from all ETL pipeline modules and loads them into Supabase PostgreSQL, respecting foreign-key dependency order.

---

## What It Does

`load.py` is a single-file loader that opens a direct `psycopg2` connection to the database and bulk-inserts rows from every pipeline module's export CSVs using `execute_values` for efficiency. It:

1. Resolves `source_name` strings in each CSV to `source_id` UUIDs via the pre-seeded `source_systems` table
2. Creates an `import_batches` record per module group (plants, compounds, diseases, targets) for provenance tracking
3. Inserts rows in FK-safe order: plants before plant_aliases, compounds before plant_compounds, etc.
4. Handles conflicts via `ON CONFLICT DO NOTHING` by default, or `ON CONFLICT DO UPDATE` with `--upsert`

The loader does **not** transform data — all canonicalization, UUID assignment, and validation must be complete before running `load.py`.

---

## Prerequisites

1. **All pipeline modules must have been run first.** The loader reads from these exact paths:

   | CSV file | Source module |
   | -------- | ------------- |
   | `plants/06_export/out/plants.csv` | `plants/` |
   | `plants/06_export/out/plant_aliases.csv` | `plants/` |
   | `compounds/07_export/out/compounds.csv` | `compounds/` |
   | `compounds/07_export/out/compound_aliases.csv` | `compounds/` |
   | `compounds/07_export/out/plant_compounds.csv` | `compounds/` |
   | `diseases/05_export/out/diseases.csv` | `diseases/` |
   | `diseases/05_export/out/disease_aliases.csv` | `diseases/` |
   | `disease_targets/05_export/out/targets.csv` | `disease_targets/` |
   | `disease_targets/05_export/out/target_aliases.csv` | `disease_targets/` |
   | `disease_targets/05_export/out/disease_targets.csv` | `disease_targets/` |

2. **`DATABASE_URL` must be set in `.env`** at the repo root. Format: `postgresql://user:password@host:port/dbname`.

3. **Activate the ETL venv** before running.

---

## Usage

```powershell
# Activate venv
etl\.venv\Scripts\Activate.ps1

# Load all 10 tables
python etl/load/load.py

# Load specific tables only
python etl/load/load.py --tables plants plant_aliases

# Load with upsert (update existing rows on conflict instead of skipping)
python etl/load/load.py --upsert

# Wipe all ETL-managed tables then reload everything fresh
python etl/load/load.py --reset
```

**`--reset`** truncates all ETL-managed tables in reverse FK order (preserving `source_systems`) then loads all tables fresh. Use this when re-running the full pipeline from scratch. `--reset` implies loading all tables and ignores `--tables` and `--upsert`.

---

## Tables Loaded

Loaded in this FK-safe order:

| Table | PK column | Source CSV |
| ----- | --------- | ---------- |
| `plants` | `plant_id` | `plants/06_export/out/plants.csv` |
| `plant_aliases` | `alias_id` | `plants/06_export/out/plant_aliases.csv` |
| `compounds` | `compound_id` | `compounds/07_export/out/compounds.csv` |
| `compound_aliases` | `compound_alias_id` | `compounds/07_export/out/compound_aliases.csv` |
| `plant_compounds` | `plant_compound_id` | `compounds/07_export/out/plant_compounds.csv` |
| `diseases` | `disease_id` | `diseases/05_export/out/diseases.csv` |
| `disease_aliases` | `disease_alias_id` | `diseases/05_export/out/disease_aliases.csv` |
| `targets` | `target_id` | `disease_targets/05_export/out/targets.csv` |
| `target_aliases` | `target_alias_id` | `disease_targets/05_export/out/target_aliases.csv` |
| `disease_targets` | `disease_target_id` | `disease_targets/05_export/out/disease_targets.csv` |

All primary keys are UUID v5 values pre-computed by the pipeline modules — the loader does not generate IDs.

---

## Expected Console Output

```
source_systems: 3 entries
Loading plants... 519
Loading plant_aliases... 597
Loading compounds... 11305
Loading compound_aliases... 73469
Loading plant_compounds... 20891
Loading diseases... 10
Loading disease_aliases... 14
Loading targets... 7589
Loading target_aliases... 22747
Loading disease_targets... 14736

Done.
```

All inserts run inside a single transaction. On any error, the transaction is rolled back and the error is printed to stderr.
