# Phase 5 — Fix All Findings

**Date:** 2026-05-23

## Summary

Classified and resolved all outstanding findings from Phases 2–4. All items either fixed or explicitly accepted with justification.

---

## Finding Inventory and Resolution

### F1 — About page methodology descriptions (frontend / documentation gap)

**Source:** Phase 2.1 adjacent issues  
**Classification:** Documentation gap  
**Status:** ✅ Fixed

- Stage 2: "Lipinski and ADME parameters" → "Lipinski RO5 + Veber rules (TPSA ≤ 140, rotatable bonds ≤ 10); natural-product exceptions apply."
- Stage 3: "reverse docking or target databases" → "ChEMBL database (pChEMBL ≥ 5.0, human targets only)."
- Stage 7: missing eigenvector centrality → added "degree, betweenness, closeness, eigenvector centrality; hub+bottleneck criterion highlights key network bridges."

**File changed:** `frontend/src/pages/AboutPage.tsx`

---

### F2 — Stage3Panel `coverage_percent` null guard (frontend)

**Source:** Phase 0C proactive audit  
**Classification:** Frontend fix  
**Status:** ✅ Already fixed (pre-existing null guard at line 61)

`(result.coverage_percent ?? 0).toFixed(1)` was already present. No change required.

---

### F3 — PipelineSidebar failed stage maps to 'future' (frontend)

**Source:** Phase 3.4 adjacent finding (obs 934)  
**Classification:** Frontend fix  
**Status:** ✅ Fixed

- `StageNavItem.tsx`: added `'failed'` to status union type; renders red `X` icon with `hf-danger` styling and left border; failed stages are clickable (show error panel).
- `PipelineSidebar.tsx`: `getStageStatus()` now returns `'failed'` instead of `'future'` when status includes `'failed'`.

**Files changed:** `frontend/src/components/pipeline/StageNavItem.tsx`, `frontend/src/components/pipeline/PipelineSidebar.tsx`

---

### F4 — Probe/temp Playwright spec files (cleanup)

**Source:** Phase 2.4 adjacent issues  
**Classification:** Cleanup  
**Status:** ✅ No action needed — files never existed in working tree

`probe-buttons.spec.ts`, `probe-after-select.spec.ts`, `probe-pipeline-complete.spec.ts`, `probe-setup.js/.cjs` not found in filesystem. Already cleaned or never committed.

---

### F5 — Vitest picking up Playwright e2e specs (test infrastructure)

**Source:** Discovered during Phase 5 test run  
**Classification:** Frontend fix  
**Status:** ✅ Fixed

Vitest had no `exclude` for `e2e/` — Playwright spec files were being executed by Vitest, producing "Playwright Test did not expect test.describe()" errors for all 5 e2e spec files.

Added `exclude: ['**/node_modules/**', '**/e2e/**']` to `vitest.config.ts`.

**File changed:** `frontend/vitest.config.ts`

---

### F6 — Integration test `getByText(/stage 8/i)` multiple match (test)

**Source:** Discovered during Phase 5 test run  
**Classification:** Frontend fix  
**Status:** ✅ Fixed

`screen.getByText(/stage 8/i)` found multiple matches (sidebar nav item + stage panel header). Changed to `screen.getAllByText(/stage 8/i)[0]`.

**File changed:** `frontend/tests/integration/pipeline-auto.test.tsx`

---

### F7 — Backend stage output key mismatches (backend / API contract)

**Source:** Phase 2.3 QA — stage panels couldn't render data  
**Classification:** Backend fix  
**Status:** ✅ Fixed (committed as backend group)

- `stage2_adme.py`: renamed response keys (`passed_count` → `passed`, etc.); added `compounds` enriched array for stage 3 chain
- `stage3_targets.py`, `stage4_disease_targets.py`, `stage7_hub_genes.py`: aligned field names with frontend types

---

### F8 — Backend models with dangling foreign keys (backend)

**Source:** Phase 1 infrastructure — backend failed to start  
**Classification:** Backend fix  
**Status:** ✅ Fixed (committed as backend group)

Removed dangling `source_id`/`source_batch_id` FK references that blocked SQLModel table creation. Registered `ImportBatch` model to resolve FK at startup.

---

### F9 — Disease ID not persisted in API responses (backend / DB)

**Source:** Phase 4.2 adjacent findings  
**Classification:** Backend / DB issue  
**Status:** ⚠️ Accepted as out-of-scope

`analysis.disease_id` returns empty string in list endpoint. Pre-existing data integrity / serialization issue. Not a regression introduced during this QA session. Logged for follow-up in a dedicated task.

---

### F10 — Frontend test-results / screenshots not gitignored (infra)

**Source:** Discovered during Phase 5  
**Classification:** Infrastructure  
**Status:** ✅ Fixed

Added to `.gitignore`:
- `frontend/test-results/`, `frontend/playwright-report/` — Playwright artifacts
- `docs/audit-session/screenshots/` — audit session screenshots
- `*.png` — screenshot files at repo root
- `.superpowers/`, `GEMINI.md` — AI tooling (internal, not project code)

Deleted spurious `nul` device file from repo root.

---

## Test Suite Verification

```
Test Files  8 passed (8)
Tests       24 passed (24)
Duration    4.89s
```

TypeScript: `tsc --noEmit` — no errors  
Build: `pnpm build` — clean (chunk size warning only, not an error)

---

## Commits

| SHA | Description |
|-----|-------------|
| `ac9ad20` | fix(backend): align stage output schemas and remove dangling FKs |
| `2cc83f5` | fix(frontend): setup form, hooks, and DataTable fixes from Phase 2 QA |
| `4d936a5` | fix(frontend): Phase 5 — sidebar failed state, about text, test suite |

---

## Phase 5 Verdict

All actionable findings from Phases 2–4 resolved. One finding (F9 — disease_id serialization) accepted as out-of-scope with justification. No remaining open items.

**QA session complete.**
