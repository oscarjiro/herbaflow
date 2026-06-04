# Backend

FastAPI backend for Herbaflow network pharmacology platform.

## Stack

- **Runtime**: Python 3.11+, managed via `uv`
- **Framework**: FastAPI + SQLModel + asyncpg (async throughout)
- **DB**: PostgreSQL via Supabase (`DATABASE_URL` in `.env`)
- **Testing**: pytest + pytest-asyncio + pytest-httpx

## Structure

```
app/
  main.py          # Entry point — CORS, routers, /health
  config.py        # Env loading, Supabase URL conversion
  database.py      # Async engine, session dependency
  models/          # SQLModel ORM (mapped to Supabase tables)
  schemas/         # Pydantic request/response validators
  routers/         # HTTP handlers — plants, compounds, diseases, analyses
  repositories/    # DB queries (data access layer)

analysis/stages/   # 8-stage pipeline (independent of HTTP layer)
  stage1_selection.py   # Compound gathering (from selected plants)
  stage2_adme.py        # ADME / Lipinski drug-likeness screening
  stage3_targets.py     # Target identification (ChEMBL)
  stage4_disease_targets.py  # Disease-specific targets (Open Targets)
  stage5_overlap.py     # Compound-disease target overlap
  stage6_ppi.py         # PPI network (STRING-DB, Cytoscape.js format)
  stage7_hub_genes.py   # Hub gene centrality analysis
  stage8_enrichment.py  # Pathway enrichment (g:Profiler)

integrations/      # External API clients (ChEMBL, Open Targets, STRING-DB, g:Profiler)
tests/
  unit/            # Mock external calls; no DB
  integration/     # Real DB; use guided mode for analysis endpoints
```

## Dev Commands

```bash
# Run server
uv run uvicorn app.main:app --reload

# Run tests
uv run pytest

# Run specific
uv run pytest tests/unit/
uv run pytest tests/integration/
```

## Conventions

- **IDs**: bare UUID strings — no type prefixes; the column name (`plant_id`, `target_id`) provides type context (see `docs/database.md`). ETL-created entities (plants, targets, compound/disease targets) use deterministic UUID v5; backend-created rows (analysis runs, target rankings, pathways, PPI edges) use UUID v4
- **Canonical keys**: `{source}:{id}` — `pubchem:678`, `chembl:CHEMBL1234`
- **Async**: all DB calls use `AsyncSession`; no sync SQLAlchemy patterns
- **Layer discipline**: routers call repositories only; pipeline stages are stateless functions
- **No direct model mutation** in routers — go through repository layer

## External APIs

| Integration       | Purpose                                        | Client                                |
| ----------------- | ---------------------------------------------- | ------------------------------------- |
| ChEMBL            | Target bioactivity (primary, pChEMBL ≥ 5.0)   | `integrations/chembl.py`              |
| PubChem BioAssay  | Secondary targets for ChEMBL-uncovered compounds (by InChIKey; aggregates BindingDB + 300+ sources) | `integrations/pubchem_bioassay.py` |
| Open Targets      | Disease-target associations                    | `integrations/open_targets.py`        |
| STRING-DB         | Protein-protein interactions                   | `integrations/stringdb.py`            |
| g:Profiler        | Pathway enrichment                             | `integrations/gprofiler.py`           |
| UniProt REST      | Human protein validation (gene symbol → accession, taxon 9606 check) | `integrations/uniprot.py` |

## Export Endpoint

`GET /analyses/{id}/export/{stage}?format=csv|json`

CSV export works for **all stages 1–8**. Each stage produces a sensible flat CSV:

| Stage | Filename pattern              | Rows                                          |
| ----- | ----------------------------- | --------------------------------------------- |
| 1     | `*_stage1_compounds.csv`      | One row per compound_id                       |
| 2     | `*_stage2_adme.csv`           | One row per compound with ADME status         |
| 3     | `*_stage3_targets.csv`        | One row per target gene                       |
| 4     | `*_stage4_disease_targets.csv`| One row per disease-associated target         |
| 5     | `*_stage5_overlap.csv`        | Summary stats + one row per overlap gene      |
| 6     | `*_stage6_ppi_edges.csv`      | One row per PPI edge                          |
| 7     | `*_stage7_hub_genes.csv`      | One row per ranked hub gene (centrality scores)|
| 8     | `*_stage8_enrichment.csv`     | One row per pathway term across GO/KEGG       |

Stage-8 enrichment rows expose `fdr` only (the Benjamini-Hochberg-corrected value
g:Profiler returns); there is no separate `p_value` column.

## Run Health & Failure Semantics

Analysis responses (`GET /analyses`, `GET /analyses/{id}`, `GET /analyses/{id}/status`)
carry derived run-health fields computed from `stage_results` at response time (no DB columns):

| Field         | Meaning                                                                 |
| ------------- | ---------------------------------------------------------------------- |
| `degraded`    | A supplementary stage ran without a provider (e.g. enrichment skipped) |
| `warnings`    | `[{stage, provider, reason}]` for each degraded stage                  |
| `has_results` | Whether the run produced compound/disease targets                      |
| `retriable`   | `failed` run whose cause was a provider outage or timeout              |

How outages route: critical providers (ChEMBL in stage 3, STRING in stage 6) fail the
run; supplementary providers (PubChem fallback in stage 3, g:Profiler in stage 8) degrade
it but let it complete. A failed run records its cause in `stage_results._run_health.failure_kind`
(`provider_unavailable` / `internal_error` / `timeout`).

A heartbeat bumps `updated_at` while a stage runs; a reaper (periodic sweep + lazy-on-read in
`get_analysis`) marks in-progress runs stale past `stale_run_threshold_seconds` as
`failed` (`timeout`). `/health` probes the DB and returns 503 when it is unreachable.

`POST /analyses/{id}/retry-enrichment` re-runs only stage 8 for a complete-but-degraded run.

## Tests

180 tests: all must pass before commit.

Unit tests mock all external APIs with `pytest-httpx`. Integration tests hit real DB — use `guided` mode for analysis endpoints to avoid external API calls mid-test.

Known: SQLAlchemy deprecation warnings from `compound_repo.py:56` — non-breaking, pre-existing.
