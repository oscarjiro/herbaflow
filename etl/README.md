# ETL — Indonesian Medicinal Plant Data Pipelines

Processes KNApSAcK plant-compound data through five sequential canonicalization modules into Supabase-ready seed tables.

## Pipeline

```
knapsack → plants → compounds → diseases → disease_targets
```

## Current Data Volume

| Entity                         | Count  |
| ------------------------------ | ------ |
| Plants (scraped)               | 535    |
| Plants (canonical)             | 519    |
| Plant-compound pairs (scraped) | 21,922 |
| Compounds (canonical)          | 11,305 |
| Compound aliases               | 73,425 |
| Plant-compound links           | 20,899 |
| Diseases (seed)                | 10     |
| Disease aliases                | 14     |
| Targets (canonical)            | 7,589  |
| Target aliases                 | 22,747 |
| Disease-target associations    | 14,736 |

## How to Run

Activate the shared virtual environment first:

```bash
# Windows
etl\.venv\Scripts\activate

# macOS/Linux
source etl/.venv/bin/activate
```

Run a full module:

```bash
python etl/plants/main.py
python etl/compounds/main.py
python etl/diseases/main.py
python etl/disease_targets/main.py
```

Run a range of stages (e.g. stages 3 through 5):

```bash
python etl/plants/main.py --start 3 --end 5
```

Dry-run (prints commands without executing):

```bash
python etl/plants/main.py --dry-run
```

## Output Files

Final outputs (Supabase import targets):

| File                                                | Description                       |
| --------------------------------------------------- | --------------------------------- |
| `plants/06_export/out/plants.csv`                   | Canonical plant records           |
| `plants/06_export/out/plant_aliases.csv`            | Plant name aliases                |
| `compounds/07_export/out/compounds.csv`             | Canonical compound records        |
| `compounds/07_export/out/plant_compounds.csv`       | Plant-compound associations       |
| `diseases/05_export/out/diseases.csv`               | Canonical disease records         |
| `diseases/05_export/out/disease_aliases.csv`        | Disease name aliases              |
| `disease_targets/05_export/out/targets.csv`         | Canonical protein targets         |
| `disease_targets/05_export/out/target_aliases.csv`  | Target gene symbol aliases        |
| `disease_targets/05_export/out/disease_targets.csv` | Disease-target association scores |

## Loading into Supabase

After all pipelines complete, load the CSVs into the database:

```bash
python etl/load/load.py                          # load all tables
python etl/load/load.py --tables compounds compound_aliases plant_compounds  # selective
```

Requires `DATABASE_URL` in `.env`. Load order follows FK dependencies automatically.

## Development

Run unit tests:

```bash
pytest etl/tests/ -v
```

See `etl/CLAUDE.md` for full conventions (settings schema, ID format, path resolution, utils split).
