# herbaflow-backend

FastAPI backend for the Herbaflow network pharmacology platform — maps Indonesian medicinal plant compounds to disease targets via an 8-stage analysis pipeline.

## Tech Stack

| Component   | Choice                              |
| ----------- | ----------------------------------- |
| Python      | 3.11+, managed with `uv`            |
| Framework   | FastAPI 0.115+                      |
| ORM         | SQLModel + SQLAlchemy 2.0 (asyncio) |
| DB driver   | asyncpg (PostgreSQL via Supabase)   |
| Testing     | pytest + pytest-asyncio + pytest-httpx |

## Quick Start

```bash
# Install dependencies
uv sync --dev

# Copy env (fill in DATABASE_URL)
cp ../.env.example .env

# Run dev server
uv run uvicorn app.main:app --reload

# Run all tests (60 total: 22 unit + 38 integration)
uv run pytest

# Unit only (no DB required)
uv run pytest tests/unit/
```

Server starts at `http://localhost:8000`. Interactive docs at `/docs`.

## Directory Structure

| Directory       | Purpose                                                        |
| --------------- | -------------------------------------------------------------- |
| `app/`          | FastAPI app — entry point, config, DB session, routers, models, schemas, repositories |
| `analysis/`     | 8-stage analysis pipeline (compound filtering → ADME → targets → disease targets → overlap → PPI → hub genes → pathway enrichment) |
| `integrations/` | External API clients: ChEMBL, Open Targets, STRING-DB, g:Profiler |
| `tests/`        | `unit/` (mocked) and `integration/` (real DB) test suites      |

## Routes

| Router      | Prefix        |
| ----------- | ------------- |
| Plants      | `/plants`     |
| Compounds   | `/compounds`  |
| Diseases    | `/diseases`   |
| Analyses    | `/analyses`   |
| Health      | `/health`     |

See `CLAUDE.md` for full development reference.
