# knapsack

Scrapes Indonesian medicinal plant entries and their associated bioactive compounds from KNApSAcK World and produces two CSV files — `plants.csv` and `plants_compounds.csv` — that seed all downstream Herbaflow ETL pipelines.

---

## Purpose in the Network Pharmacology Workflow

The Herbaflow pipeline answers a classic network pharmacology question: which bioactive compounds in Indonesian medicinal plants share molecular targets with diseases of interest? Before any compound canonicalization, taxonomy normalization, or target overlap analysis can occur, the raw plant-compound pairs must be collected. The `knapsack/` module performs that collection.

This module is Step 1 in the Herbaflow ETL sequence:

```
knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/
```

It is the sole source of truth for which plant species are in scope and which KNApSAcK compound records are associated with them. Every entity that subsequently flows through the pipeline — canonical plant entries, PubChem-enriched compounds, disease-target overlaps — traces its lineage back to the plant-compound pairs produced here.

KNApSAcK World was chosen because it is an evidence-based, curated database of plant-metabolite associations compiled from primary literature. Its Indonesian-origin filter (`cn=IDN`) restricts the discovery set to species recorded as growing or used medicinally in Indonesia, which is the geographic scope of this study. Unlike automated text-mining databases, KNApSAcK entries are manually curated with explicit literature references, making them appropriate as a primary source for a network pharmacology study.

The outputs of this module feed two downstream pipelines directly:

- `plants/` consumes `plants.csv` and canonicalizes species names against the GBIF backbone taxonomy
- `compounds/` consumes `plants_compounds.csv` and enriches compound records via PubChem and ChEMBL

---

## Data Source

**Name:** KNApSAcK World
**URL:** https://www.knapsackfamily.com/KNApSAcK_World/search.php?cn=IDN

KNApSAcK World is a publicly accessible, freely available plant metabolite database maintained by the Nara Institute of Science and Technology (NAIST) and collaborators. It aggregates plant-compound associations from peer-reviewed literature with an emphasis on Asian plant species.

| Evidence type          | Description                                                                  |
| ---------------------- | ---------------------------------------------------------------------------- |
| Primary literature     | Journal articles documenting metabolite isolation or detection               |
| Ethnobotanical records | Traditional use records documented in regional pharmacopoeia                 |
| Reference books        | Regional plant resource compendia (e.g., Plant Resources of South-East Asia) |

The database is free to access and does not require authentication. The scraper applies rate-limiting (see `scraper.request_delay_seconds` in settings) to respect the server. The `cn=IDN` filter returns only species with Indonesian geographic origin, and the scraper additionally filters for rows with `purpose = "medicinal"` to exclude food and non-medicinal entries.

---

## Pipeline Steps (Logical Phases)

This module is a single-file scraper (`main.py`) with no staged subdirectories. It executes four logical phases in sequence.

---

### Phase 1 — Discover

**Input:** KNApSAcK World index page filtered to Indonesian medicinal plants
(`https://www.knapsackfamily.com/KNApSAcK_World/search.php?cn=IDN&wd=&flg=`)

**What it does:**

1. Fetches the index page HTML via an HTTP GET request
2. Locates the main species table (by `id="tablekit-table-1"` or by column header heuristic)
3. Iterates every data row, skipping header rows and any row where `purpose != "medicinal"`
4. Extracts the species name from the first `<td>` using only direct text nodes (ignores icon links)
5. Extracts the KNApSAcK Core detail URL for each species — specifically links matching `knapsack_core/result.php?sname=organism`
6. Deduplicates by `detail_url`; rows without a detail URL are skipped when `--require-detail-url` is set (default: `True`)
7. Collects family name, common name, classification, purpose, and literature reference per row

**Output:** In-memory list of plant records (written to `plants.csv` immediately after this phase)

---

### Phase 2 — Scrape

**Input:** List of plant records with `detail_url` populated

**What it does:**

1. For each plant, issues a GET request to its KNApSAcK Core detail page
2. Applies the configured `REQUEST_DELAY` between requests to avoid overloading the server
3. Retries on transient HTTP errors (429, 500, 502, 503, 504) using exponential backoff — up to `MAX_RETRIES` attempts
4. Logs URLs that fail all retries to `failed_pages.txt` for manual review
5. Passes the response HTML to Phase 3 for parsing

**Output:** Raw BeautifulSoup document per plant page

**Checkpoint / resume behavior:** If `--resume` is passed, the scraper reads existing `plant_id` values from `plants_compounds.csv` and skips those plants, appending only new rows. Without `--resume`, the output file is overwritten from scratch. Results are flushed to disk after every plant to minimize data loss on interruption.

---

### Phase 3 — Parse

**Input:** Raw HTML from each plant's KNApSAcK Core detail page

**What it does:**

1. Locates the compound table on the page — identified by presence of `C_ID`, `Metabolite`, or `C ID` text in the first few cells, or by a regex match for KNApSAcK compound IDs (`C\d{8}`) in the first three rows
2. Extracts one compound record per table row: KNApSAcK C_ID, CAS registry number, metabolite name, molecular formula, molecular weight, and organism name
3. Deduplicates compound rows within the page by `c_id` (preferred) or full row signature if `c_id` is absent
4. Associates each compound row with its parent plant via `plant_id`

**Output:** In-memory list of compound rows for the current plant

---

### Phase 4 — Save

**Input:** All compound rows collected across all plants; plant list from Phase 1

**What it does:**

1. Writes `plants.csv` using pandas (UTF-8 BOM encoding for Excel compatibility)
2. Writes `plants_compounds.csv` row-by-row using `csv.DictWriter` with incremental `f.flush()` after each plant, so partial results survive interruption
3. Writes a `failed_pages.txt` log of any URLs that could not be fetched

**Output:** `out/plants.csv`, `out/plants_compounds.csv`, `out/failed_pages.txt`

---

## Output Schema Reference

### `out/plants.csv`

One row per unique medicinal plant species found in KNApSAcK World for Indonesia. This file seeds `plants/01_extract/` for taxonomy canonicalization.

| Column           | Description                                                                                                             |
| ---------------- | ----------------------------------------------------------------------------------------------------------------------- |
| `plant_id`       | Sequential integer assigned during this scrape run (1, 2, 3, …). Not a stable UUID — `plants/` assigns canonical UUIDs. |
| `species_name`   | Scientific species name extracted from the plain text of the species cell (excludes icon links)                         |
| `family_name`    | Botanical family name (e.g., `Malvaceae`, `Fabaceae`)                                                                   |
| `common_name`    | Common/vernacular name(s), pipe-separated when multiple are listed                                                      |
| `classification` | KNApSAcK classification string (e.g., `plants`, `plants(vegetables)`)                                                   |
| `purpose`        | Always `medicinal` — non-medicinal rows are filtered out during Phase 1                                                 |
| `reference`      | Literature reference(s) supporting the entry, as formatted by KNApSAcK                                                  |
| `detail_url`     | Full URL to the KNApSAcK Core page listing this species' compounds                                                      |

These outputs are **not** final database-ready records. They do not carry UUID primary keys and the `species_name` values are raw KNApSAcK strings that have not been validated against any taxonomy backbone. The `plants/` module handles taxonomy normalization and UUID assignment.

---

### `out/plants_compounds.csv`

One row per unique plant-compound pair. Multiple rows share the same `plant_id` for plants with several compounds. This file seeds `compounds/01_extract/` for compound canonicalization.

| Column              | Description                                                                                                                  |
| ------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| `plant_id`          | FK to `plants.csv` — matches the sequential integer assigned in this run                                                     |
| `c_id`              | KNApSAcK compound identifier (e.g., `C00001071`) — 8-digit zero-padded integer with `C` prefix                               |
| `cas_id`            | CAS Registry Number (e.g., `529-44-2`); may be empty for novel or unregistered compounds                                     |
| `metabolite`        | Compound name as given by KNApSAcK (e.g., `Myricetin`, `Quercetin 3-O-alpha-L-rhamnoside`)                                   |
| `molecular_formula` | Molecular formula string (e.g., `C15H10O8`)                                                                                  |
| `mw`                | Molecular weight (monoisotopic mass as a float string)                                                                       |
| `organism`          | Scientific species name as recorded on the KNApSAcK compound detail page; may differ slightly from `plants.csv.species_name` |

These outputs are also **not** final database-ready records. The `compounds/` module enriches them via PubChem and ChEMBL lookups, deduplicates across plants, and assigns canonical UUIDs.

---

## Configuration (`settings.yml`)

All settings live in `etl/knapsack/settings.yml`. After the settings-wiring fix, every `scraper.*` key is read at startup and used by the scraper at runtime.

| Key                             | Default                               | Description                                                        |
| ------------------------------- | ------------------------------------- | ------------------------------------------------------------------ |
| `module.name`                   | `knapsack`                            | Module identifier used in logging                                  |
| `source.name`                   | `KNApSAcK World`                      | Display name propagated to downstream records                      |
| `source.url`                    | _(index URL)_                         | Full URL of the Indonesia-filtered index page                      |
| `source.batch_id`               | `knapsack_world_id_2026_04_17`        | Batch identifier for provenance tracking                           |
| `paths.output_dir`              | `knapsack/out`                        | Output directory, relative to `etl/`                               |
| `paths.plants_file`             | `plants.csv`                          | Filename for the plant list output                                 |
| `paths.plants_compounds_file`   | `plants_compounds.csv`                | Filename for the plant-compound pairs output                       |
| `paths.failed_pages_log`        | `failed_pages.txt`                    | Log file for URLs that failed all retries                          |
| `paths.scraper_log`             | `scraper.log`                         | Log file name (used by `setup_logging`)                            |
| `export.format`                 | `csv`                                 | Output format                                                      |
| `export.encoding`               | `utf-8`                               | File encoding (written as `utf-8-sig` for Excel BOM compatibility) |
| `scraper.request_delay_seconds` | `1.2`                                 | Seconds to sleep between plant detail page requests                |
| `scraper.max_retries`           | `3`                                   | Maximum retry attempts for failed HTTP requests                    |
| `scraper.timeout_seconds`       | `30`                                  | Per-request HTTP timeout in seconds                                |
| `scraper.user_agent`            | `indonesian-medicinal-plants-etl/1.0` | `User-Agent` header sent with every request                        |

---

## How to Run

**Prerequisites:** Activate the ETL virtual environment before running.

```powershell
# From repo root
etl\.venv\Scripts\Activate.ps1
```

**Full scrape (fresh run, overwrites output):**

```powershell
python etl/knapsack/main.py
```

**Resume an interrupted run (append only, skip already-processed plants):**

```powershell
python etl/knapsack/main.py --resume True
```

**Relax the detail URL requirement (include plants without a KNApSAcK Core link):**

```powershell
python etl/knapsack/main.py --require-detail-url False
```

**Expected console output on a successful run:**

```
2026-05-17 06:00:00 | INFO | Scraping medicinal plants from Indonesia filter page...
2026-05-17 06:00:02 | INFO | Found 412 unique medicinal plants
2026-05-17 06:00:02 | INFO | Saved plant list to .../knapsack/out/plants.csv
2026-05-17 06:00:02 | INFO | [FRESH] Starting a new compounds file.
2026-05-17 06:00:03 | INFO | [1/412] Abelmoschus manihot: 14 compounds
2026-05-17 06:00:04 | INFO | [2/412] Abelmoschus moschatus (L.) Medic.: 5 compounds
...
2026-05-17 06:XX:XX | INFO | Done. Results saved to .../knapsack/out/plants_compounds.csv
2026-05-17 06:XX:XX | INFO | Failed pages log: .../knapsack/out/failed_pages.txt
```

The scrape takes several minutes depending on plant count and network latency (approximately `n_plants × request_delay_seconds` as a lower bound).

---

## Output Interpretation

**`plants.csv`** contains one row per unique Indonesian medicinal plant species discovered on the KNApSAcK World index page. The `detail_url` column is the stable lookup key used to associate each plant with its compounds.

**`plants_compounds.csv`** contains one row per unique plant-compound pair. A single plant may have zero to several hundred compound rows depending on how thoroughly it has been studied. Compounds are identified by KNApSAcK `c_id` at this stage — PubChem InChIKey and canonical identifiers are assigned by the `compounds/` pipeline.

**Expected row counts** (based on a full Indonesia-filtered medicinal scrape):

- `plants.csv`: ~400 rows (depends on current KNApSAcK World content)
- `plants_compounds.csv`: several thousand rows (varies; well-studied plants such as _Curcuma longa_ contribute dozens of compounds)

**What to verify after a run:**

- `failed_pages.txt` should be empty or contain only a small number of transient failures — rerun with `--resume True` to retry them
- Row count in `plants_compounds.csv` should be substantially larger than `plants.csv` (typically 5–20× more)
- Spot-check: `plant_id = 1` in both files should correspond to the same species name

---

## Idempotency

Running `main.py` without `--resume` is a full overwrite: both `plants.csv` and `plants_compounds.csv` are recreated from scratch, and `failed_pages.txt` is cleared. The `plant_id` counter restarts at 1 on each fresh run. Because these IDs are sequential integers (not UUID v5), they are **not stable across runs** — the canonical stable IDs are assigned by the `plants/` and `compounds/` modules downstream.

Running with `--resume True` appends to the existing `plants_compounds.csv`, skipping any `plant_id` values already present. `plants.csv` is still overwritten on every run (it is written before the resume checkpoint is checked).

There is no HTTP response cache — each run fetches all pages live. To avoid re-scraping, use `--resume True` to continue an interrupted run rather than starting from scratch.
