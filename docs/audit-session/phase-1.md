# Phase 1 — Infrastructure Boot Audit Log

## Task 1.1 — Backend startup

- **Command:** `uv run uvicorn app.main:app --reload --port 8000` (from /backend/)
- **Result:** `GET /health → {"status":"ok","version":"0.1.0"}` ✓
- **DATABASE_URL:** configured in .env, Supabase pooler

## Task 1.2 — Playwright browsers

- **Command:** `pnpm exec playwright install --with-deps chromium`
- **Result:** Chromium installed ✓

## Task 1.3 — API contract spot-check

| Endpoint | Expected fields | Actual | Match |
|----------|----------------|--------|-------|
| GET /plants | plant_id, canonical_scientific_name, family_name, compound_count | ✓ all present | ✓ |
| GET /diseases | disease_id, disease_name, ontology_id | ✓ all present (+ ontology_source) | ✓ |
| POST /analyses | returns analysis_id | ✓ `{"analysis_id":"...","status":"pending",...}` | ✓ |
| GET /analyses/:id/status | status string format | `stage_1_awaiting_approval` — matches `isAwaitingApproval` pattern | ✓ |

## Bug Found and Fixed

- **BUG:** `AnalysisStatus` type in `frontend/src/types/api.ts` was missing `stage_1_awaiting_approval` — all other stages (2–8) had it. The backend returns this status for Stage 1 in guided mode (confirmed in live test).
- **Fix:** Added `| 'stage_1_awaiting_approval'` after `stage_1_failed` in the union type.
- **File changed:** `frontend/src/types/api.ts`

## Adjacent Issues

- `disease_ids` field name in `CreateAnalysisRequest` is an array (correct per backend schema). Test POST accidentally used `disease_id` (singular) — the analysis ran with empty disease_ids due to default `= []`. No type mismatch.
- `family_name` on some plants is empty string (e.g., "Abelmoschus manihot"). Possible data quality issue — logged, not blocking QA.
