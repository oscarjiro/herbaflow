# Herbaflow

Network pharmacology platform for Indonesian medicinal plants. Maps plant-compound-disease-target
relationships from the KNApSAcK database.

## Stack
- **Backend**: FastAPI (Python) — `/backend/`
- **Frontend**: React — `/frontend/` (not yet implemented)
- **Database**: PostgreSQL via Supabase — schema reference: @.claude/docs/database.md
- **ETL**: Python pipelines — `/etl/`

## Directory Map
| Path | Status | Purpose |
|------|--------|---------|
| `/etl/` | Active | Data ingestion and canonicalization pipelines |
| `/backend/` | Early stage | FastAPI REST API |
| `/frontend/` | Not started | React UI (placeholder only) |

## Key Conventions
- All data identifiers are domain-prefixed strings: `pl_`, `al_`, `tgt_`, `dtg_`, etc.
- Canonical keys use `{source}:{id}` format: `gbif:12345`, `pubchem:678`
- ETL outputs live in `out/` within each step directory — not edited directly
- Module config lives in `settings.yml` at each module root

## Git Workflow
- Before any `git commit` or `git push`: confirm scope and commit message with the user first
- Use Conventional Commits format: `type(scope): imperative summary`
- Never commit without explicit user approval of the message

## Do Not Touch
- Any `.env` or `.env.*` files
- `etl/**/.venv/` virtual environments
- `.claude/settings.local.json`
- `etl/**/out/` CSV files — only the pipeline scripts should write these
