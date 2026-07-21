# Herbaflow

Network-pharmacology platform for Indonesian medicinal plants. Maps plant, compound, disease, and
target relationships sourced from KNApSAcK, runs an 8-stage analysis pipeline, and exports results
for downstream tools.

`/backend` and `/frontend` are the deployed application: backend on Render, frontend on Vercel,
database on Supabase.

## Source of truth (strict precedence)

1. **The live database** (Supabase) — ground truth for what data exists.
2. **`/shared/contracts/analysis.json`** (JSON Schema) — the single upstream source for pipeline
   enums, parameter ranges, and run status. The backend loads it via `app/contracts.py`; the
   frontend consumes the generated copy. Never restate a bound in code that the contract owns.
3. **`/docs`** — `database.md` (schema), `frontend.md`, `security.md`, `testing.md`,
   `ctp-network.md`, `observability.md`. Kept in sync with the code that changes.
4. **The package `CLAUDE.md` files** — `backend/`, `frontend/`, and `etl/` each document their own
   canonical homes in far more detail than this file.
5. **`docs/design-system/`** — visual style only. Never a source for science or workflow.

## Stack

- Backend: FastAPI + SQLAlchemy 2.0 (async) + Pydantic v2 — `/backend`, run with `uv`.
- Frontend: React 19 + TypeScript + Vite — `/frontend`, run with `pnpm`.
- Database: PostgreSQL via Supabase; migrations in `/supabase/migrations`, schema in `docs/database.md`.
- ETL: `/etl` — the data-source pipelines (plants, compounds, diseases, disease targets) that seed
  the database. Run manually, not part of the served application.

## Non-negotiable conventions

- One canonical home per concern. Logic needed in two or more places is extracted once and imported;
  never copy-pasted into a second variant.
- Frontend wire types are **generated** from the backend OpenAPI schema (`@hey-api/openapi-ts`) and
  never hand-written. The codegen drift gate fails the build if they go stale.
- All datetime columns are `DateTime(timezone=True)`; the application uses timezone-aware UTC.
- Errors are RFC 9457 `application/problem+json`; success bodies are plain JSON.
- No silent drops: every rejected input is reported with a reason.
- Organism is human-only (taxon 9606), fixed.
- Update the relevant `CLAUDE.md` and `docs/` files (including `docs/database.md`) in the **same
  change** as the code.

## Gates (must be green to merge)

- Backend: `ruff`, `black --check`, `mypy app`, `pytest`.
- Frontend: `eslint`, `prettier --check`, `tsc --strict`, `vitest`.
- Codegen drift: `python scripts/check_codegen_drift.py`.

## Git

Conventional Commits. Confirm scope and message before committing or pushing.
