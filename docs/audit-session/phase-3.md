# Phase 3 — Edge Cases Audit Log

## Task 3.1 — Rejection Flow

**Date:** 2026-05-22

**Found:**
- `PipelinePage.tsx` had no handling for `stage_N_rejected` terminal status
- Only `failed` status had a dedicated UI (via `ErrorState` component)
- `AnalysisStatus` union in `types/api.ts` was missing all 8 `stage_N_rejected` variants — the `(string & {})` catch-all masked this gap

**Fixed:**
1. `frontend/src/pages/PipelinePage.tsx` — added rejected-state block (lines 124–146):
   - Detects `/^stage_\d+_rejected$/` regex (not `endsWith` — prevents false positives)
   - Parses stage number from status string for contextual message
   - "Start New Analysis" button: clears `hf_last_analysis_id` localStorage key, navigates to `/analysis`
   - Button has `type="button"` (accessibility)
   - Uses only `hf-*` Tailwind tokens
2. `frontend/src/types/api.ts` — added `stage_1_rejected` through `stage_8_rejected` variants to `AnalysisStatus` union

**TypeScript:** `tsc --noEmit` clean after fixes.

**Adjacent bug found (proactive):**
- `isTerminalStatus()` in `types/api.ts:95` already correctly matches `rejected$` — no change needed there.
- `SetupPage.tsx` cache restore correctly does NOT redirect rejected analyses (uses `isTerminalStatus` guard) — behaviour already correct.

**Files changed:**
- `frontend/src/pages/PipelinePage.tsx`
- `frontend/src/types/api.ts`

---

## Task 3.6 — Zero Overlap: Downstream Empty States (Stages 6–8)

**Date:** 2026-05-23

**Context:** If Stage 5 yields 0 overlap genes, Stages 6–8 receive empty gene lists. Stage 5 already shows a critical warning (added Phase 2.3). This task verifies Stages 6–8 don't crash.

**Stage 6 — PPI Network:**
- `elements` memo: `result ? [...result.nodes, ...result.edges] : []` → empty array
- CytoscapeComponent renders with `elements=[]` → empty canvas, no crash ✓
- `node_count: 0`, `edge_count: 0` shown in StatCards correctly ✓

**Stage 7 — Hub Gene Analysis:**
- `result.hub_genes = []` → `hubCount = 0` ✓
- `DataTable data={[]}` → `paginated.length === 0` → "No results" row rendered ✓
- No crash path identified ✓

**Stage 8 — Pathway Enrichment:**
- `PathwayChart` line 33: `if (terms.length === 0)` → `EmptyState` per tab ✓
- `termsBySource` uses `?? []` null-coalescing for all 4 sources ✓
- All tabs show EmptyState independently — correct granularity ✓

**Fixed:** No code change required — all three panels already handle zero-data gracefully.

**Files changed:** None.

---

## Task 3.5 — Backend Unreachable Mid-Analysis

**Date:** 2026-05-22

**Found:**
- `PipelinePage.tsx` destructured only `data` from `useAnalysisStatus` — `isError` was ignored
- TanStack Query retries 3× silently; after exhaustion, error state was swallowed with no UI feedback
- User saw a blank/loading pipeline page indefinitely when backend went down mid-analysis

**Fixed:**
- `PipelinePage.tsx` line 99: added `isError: statusError` to destructure
- Added `statusError` guard block before the main render — shows `ErrorState` with message "Unable to reach the server. Check that the backend is running."
- "New Analysis" CTA in error state clears localStorage and navigates to `/analysis`
- Placed after `failed` and `rejected` guards, before the layout render

**Note — UX gap (acceptable, logged):**
- No distinction between "stage failed in pipeline" vs "API unreachable" — both route through `ErrorState`. For the scope of this QA session this is acceptable; a follow-up could differentiate based on `status.error_message` vs network error.

**TypeScript:** `tsc --noEmit` clean.

**Files changed:**
- `frontend/src/pages/PipelinePage.tsx`

---

## Task 3.4 — New Analysis After Completion

**Date:** 2026-05-22

**Found:**
- `PipelineSidebar.tsx` lines 53–56: `handleNewAnalysis()` already implemented
- Clears `hf_last_analysis_id` from localStorage, then `navigate('/analysis')`
- Button in footer (lines 96–102): `type="button"`, correct tokens, always visible regardless of pipeline status

**Fixed:** No code change required — already correctly implemented.

**Adjacent bug noted (proactive, out of scope):**
- `getStageStatus()` line 32: maps `failed` stage to `'future'` nav state — failed stages show no error indicator in sidebar. Already logged (obs 934). Should be addressed in a follow-up.

**Files changed:** None.

---

## Task 3.3 — Cache Restore (Valid Completed Analysis ID)

**Date:** 2026-05-22

**Found:**
- `SetupPage.tsx` line 45: `if (!isTerminalStatus(status.status))` never redirected for `'complete'` analyses
- `isTerminalStatus('complete')` returns `true` (matches `complete$` regex) → `!true = false` → `navigate()` never called
- Users with a completed analysis ID in localStorage saw the blank setup form instead of the finished pipeline
- `failed` and `stage_N_rejected` statuses correctly stayed on setup page (intended — user should restart)

**Fixed:**
- `SetupPage.tsx` line 45: changed condition to `!isTerminalStatus(status.status) || status.status === 'complete'`
- Redirects for: in-progress analyses (not terminal) AND successfully completed analyses
- Stays on setup form for: `failed`, `stage_N_rejected` (user should start fresh)

**TypeScript:** `tsc --noEmit` clean.

**Files changed:**
- `frontend/src/pages/SetupPage.tsx`

---

## Task 3.2 — Stale localStorage (Invalid Analysis ID)

**Date:** 2026-05-22

**Found:**
- `SetupPage.tsx` already handles this correctly via its `useEffect` cache-restore block (lines 39–53)
- `api.request()` throws `Error("API 404: ...")` on non-2xx responses
- 404 → `.catch()` fires → `localStorage.removeItem('hf_last_analysis_id')` → stays on setup form
- Network error (backend unreachable) → `fetch` itself throws → same `.catch()` path
- No flash/flicker: form renders immediately on mount; the async check runs post-mount; user always sees the setup form while the check is in flight

**Fixed:** No code change required — already correctly handled.

**Files changed:** None.

---
