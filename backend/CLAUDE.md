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

## Tests

60 tests: 22 unit + 38 integration. All must pass before commit.

Unit tests mock all external APIs with `pytest-httpx`. Integration tests hit real DB — use `guided` mode for analysis endpoints to avoid external API calls mid-test.

Known: SQLAlchemy deprecation warnings from `compound_repo.py:56` — non-breaking, pre-existing.
