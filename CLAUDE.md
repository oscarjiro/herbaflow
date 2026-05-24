# Herbaflow

Network pharmacology platform for Indonesian medicinal plants. Maps plant-compound-disease-target
relationships from the KNApSAcK database.

## Stack

- **Backend**: FastAPI (Python) — `/backend/`
- **Frontend**: React 18 + TypeScript + Vite — `/frontend/`
- **Database**: PostgreSQL via Supabase — schema reference: `docs/database.md`, always update everytime a schema change is done
- **ETL**: Python pipelines — `/etl/`

## Directory Map

| Path                    | Status      | Purpose                                              |
| ----------------------- | ----------- | ---------------------------------------------------- |
| `/etl/`                 | Active      | Data ingestion and canonicalization pipelines        |
| `/backend/`             | Active      | FastAPI REST API — 8-stage pipeline, 60 tests        |
| `/frontend/`            | Active      | React 18 + TS SPA — 8-stage pipeline UI              |
| `/supabase/migrations/` | Active      | All Supabase SQL migrations (single source of truth) |

## Key Conventions

- All entity primary keys are bare UUID v5 strings (no type prefixes); column names (`plant_id`, `target_id`) provide type context — see `docs/database.md`
- Canonical keys use `{source}:{id}` format: `gbif:12345`, `pubchem:678`
- ETL outputs live in `out/` within each step directory — not edited directly
- Module config lives in `settings.yml` at each module root
- After any migration (ADD COLUMN, DROP COLUMN, ALTER TYPE, new table, drop table) — update `docs/database.md` to reflect the final schema state

## Git Workflow

- Before any `git commit` or `git push`: confirm scope and commit message with the user first
- Use Conventional Commits format: `type(scope): imperative summary`
- Never commit without explicit user approval of the message

## Do Not Touch

- Any `.env` or `.env.*` files
- `etl/**/.venv/` virtual environments
- `.claude/settings.local.json`
- `etl/**/out/` CSV files — only the pipeline scripts should write these
