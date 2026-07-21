# Herbaflow

Herbaflow is a network-pharmacology platform for Indonesian medicinal plants. It maps the
relationships between plants, their compounds, protein targets, and diseases, then runs an 8-stage
analysis pipeline and exports the results in formats other research tools can read.

Live application: https://herbaflow-oscarjiro.vercel.app

## What it does

Network pharmacology asks which proteins a plant's compounds act on, and whether those proteins
overlap with the proteins implicated in a disease. Herbaflow automates that question end to end:

1. **Compound collection** gathers the compounds reported for the selected plants.
2. **Drug-likeness screening** computes ADME descriptors and applies Lipinski and Veber rules, with a
   natural-product exception and a PAINS alert reported alongside.
3. **Compound to target identification** finds measured bioactivities from ChEMBL and PubChem BioAssay.
4. **Disease to target collection** reads the Open Targets associations seeded for the disease.
5. **Overlap** intersects the two target sets. This is the raw shared set, with no scoring applied.
6. **Protein interaction network** builds a STRING network over the shared targets.
7. **Hub ranking** ranks proteins by Maximal Clique Centrality (Chin et al., 2014), and reports four
   classic centrality measures alongside it.
8. **Functional enrichment** tests the shared targets against the compound-target universe using
   g:Profiler.

Runs can be driven stage by stage with an approval checkpoint at each step, or executed automatically
to completion. Results download as per-stage CSVs, publication-oriented figures, a Markdown report,
and Cytoscape-importable network files.

You can also skip the earlier stages by entering compounds (as SMILES or InChIKey) or protein targets
(as gene symbols or UniProt accessions) directly.

## Stack

| Layer | Technology | Location |
|---|---|---|
| Backend | FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, run with `uv` | `/backend` |
| Frontend | React 19, TypeScript, Vite, TanStack Router/Query/Table, Tailwind v4 | `/frontend` |
| Database | PostgreSQL on Supabase | `/supabase/migrations` |
| Data pipelines | Python ETL sourcing KNApSAcK, GBIF, PubChem, Open Targets | `/etl` |
| Contract | JSON Schema shared by both sides | `/shared/contracts/analysis.json` |

The frontend's API types are generated from the backend's OpenAPI schema, and a drift gate fails the
build if they fall out of sync.

## Repository layout

```
backend/    FastAPI service and the 8-stage pipeline
frontend/   React single-page application
etl/        Data pipelines that seed the database (run manually, not part of the service)
shared/     The analysis contract consumed by both sides
supabase/   Database migrations
docs/       Schema, frontend, security, testing, and validation documentation
scripts/    Codegen drift gate and related tooling
```

## Running locally

Requires Python with [uv](https://docs.astral.sh/uv/), Node with pnpm, and a PostgreSQL connection
string in `.env` as `DATABASE_URL`.

```bash
# Backend, serves on http://localhost:8000
cd backend
uv sync
uv run uvicorn app.main:app --reload

# Frontend, serves on http://localhost:5173
cd frontend
pnpm install
pnpm dev
```

## Tests and checks

```bash
# Backend
cd backend && uv run ruff check . && uv run black --check . && uv run mypy app && uv run pytest

# Frontend
cd frontend && pnpm lint && pnpm format:check && pnpm typecheck && pnpm test

# Shared
python scripts/check_codegen_drift.py
```

Backend integration tests start a throwaway PostgreSQL container, so Docker needs to be running for
those. Unit tests do not require it.

## Data sources

Plant and compound records come from KNApSAcK, with plant taxonomy resolved against GBIF. Compound
structures and properties come from PubChem and RDKit. Bioactivities come from ChEMBL and PubChem
BioAssay. Disease-to-target associations come from Open Targets. Protein interactions come from
STRING, and functional enrichment from g:Profiler. Every stored record carries its source name,
source URL, and retrieval timestamp.

## Status

Herbaflow was built as an undergraduate thesis project and is complete and deployed. Open work is
tracked in [GitHub Issues](https://github.com/oscarjiro/herbaflow/issues).

## Documentation

- [`docs/database.md`](docs/database.md) — schema reference
- [`docs/frontend.md`](docs/frontend.md) — frontend architecture
- [`docs/security.md`](docs/security.md) — security posture and OWASP walk-through
- [`docs/testing.md`](docs/testing.md) — test strategy
- [`docs/ctp-network.md`](docs/ctp-network.md) — compound-target-pathway network
- [`docs/validation/`](docs/validation) — validation runs against published studies
