# Cross-stack contracts

Language-neutral JSON consumed by **both** stacks. This is the single upstream source for
analysis-domain vocabularies and pipeline-parameter bounds.

- **Backend** (`/backend`, Python) reads the contract through `app/contracts.py` (vocabularies +
  parameter bounds). This is the backend read side.
- **Frontend** (`/frontend`, TypeScript) will consume the same file via its own reader; that half
  arrives with the components that need it.

Changing a value here changes every layer that consumes it. The matching DB `CHECK` constraint
lives in `supabase/migrations/` and is verified against the contract by an agreement test
(`backend/tests/test_contract_agreement.py`).

| File | Defines |
|---|---|
| `analysis.json` | JSON Schema (draft 2020-12). `$defs`: `mode` (`analysis_runs.mode`), `stage_state`, `run_status_flat` + `stage_phase` (the run-status vocabulary; the DB column stays free text), and `pipeline_parameters` bounds. |
