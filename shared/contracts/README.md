# Cross-stack contracts

Language-neutral JSON consumed by **both** stacks:

- **Backend** (`/backend`, Python) loads these at import — see `app/contracts.py`.
- **Frontend** (`/frontend`, TypeScript) imports them via the `@shared` alias.

Changing a list here changes every layer that consumes it. The matching DB `CHECK` constraint lives in
`supabase/migrations/` and is verified against the relevant file by agreement tests
(`backend/tests/unit/test_contract_mode.py`, `frontend/src/lib/contracts.test.ts`).

| File | Defines |
|---|---|
| `analysis.json` | `analysis_mode` — allowed values for `analysis_runs.mode`. |
