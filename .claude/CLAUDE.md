# Project-Local Claude Overrides

## .env Permission Override

Claude MAY read and write `.env` and `.env.*` files in this project.
This overrides the global CLAUDE.md restriction for this project only.
Reason: DATABASE_URL is needed for etl/load/load.py and Supabase CLI setup.

## Scope

This applies only to `C:\code\web\herbaflow\.env` (and `.env.local`, `.env.example`).
Never commit `.env` to git — it contains database credentials.
