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
  stage1_selection.py   # Compound filtering (Lipinski)
  stage2_adme.py        # ADME prediction
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

- **IDs**: domain-prefixed strings — `pl_`, `al_`, `tgt_`, `dtg_`
- **Canonical keys**: `{source}:{id}` — `pubchem:678`, `chembl:CHEMBL1234`
- **Async**: all DB calls use `AsyncSession`; no sync SQLAlchemy patterns
- **Layer discipline**: routers call repositories only; pipeline stages are stateless functions
- **No direct model mutation** in routers — go through repository layer

## External APIs

| Integration  | Purpose                      | Client                         |
| ------------ | ---------------------------- | ------------------------------ |
| ChEMBL       | Target bioactivity           | `integrations/chembl.py`       |
| Open Targets | Disease-target associations  | `integrations/open_targets.py` |
| STRING-DB    | Protein-protein interactions | `integrations/stringdb.py`     |
| g:Profiler   | Pathway enrichment           | `integrations/gprofiler.py`    |

## Tests

60 tests: 22 unit + 38 integration. All must pass before commit.

Unit tests mock all external APIs with `pytest-httpx`. Integration tests hit real DB — use `guided` mode for analysis endpoints to avoid external API calls mid-test.

Known: SQLAlchemy deprecation warnings from `compound_repo.py:56` — non-breaking, pre-existing.
