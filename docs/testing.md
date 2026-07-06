# HerbaFlow Testing Methodology

## Test Types

| Type | Tool | Location | Coverage target |
|---|---|---|---|
| Unit (backend) | pytest | `backend/tests/unit/` | ≥80% business logic |
| Integration (backend) | pytest | `backend/tests/integration/` | All API endpoints |
| Component / unit (frontend) | Vitest | Colocated `frontend/src/**/*.test.tsx` next to each component/hook | ≥80% components/hooks |
| Integration (frontend) | Vitest + MSW | Flat `frontend/tests/` (view-level flows, contract, static SEO) | Pipeline flows |
| Scientific acceptance | pytest | `backend/tests/scientific/` | Full pipeline with reference data |

The frontend has no separate `unit/`, `integration/`, or `e2e/` subfolders. Most tests are
colocated with their component under `frontend/src/`, and `frontend/tests/` is a flat folder of
view-level integration tests (`SetupView`, `Stage2View`, `Stage3View`, `contract`, `staticSeo`,
`indexHtml`, `lint-danger`) plus the shared MSW handlers (`handlers.ts`), the router test helper
(`renderWithRouter.tsx`), and the Vitest setup (`setup.ts`). All frontend tests run under a single
Vitest command. End-to-end coverage against a running stack is exercised manually, not by a
committed frontend E2E suite.

## Running Tests

### Backend unit tests
```bash
cd backend && uv run pytest tests/unit/ -v
```

### Backend with coverage
```bash
cd backend && uv run pytest --cov=analysis --cov=app --cov=integrations --cov-report=term-missing -q
```

### Frontend tests (colocated + integration)
```bash
cd frontend && pnpm test
```

This runs `vitest run` across both the colocated `src/**/*.test.tsx` tests and the flat
`frontend/tests/` integration tests. Add `--coverage` for a coverage report.

### End-to-end proof (manual, requires running stack)

There is no committed frontend E2E suite. End-to-end behavior is verified by driving the real UI
against a running backend and database:
```bash
# Start backend (separate terminal):
cd backend && uv run uvicorn app.main:app --reload

# Start frontend dev server (separate terminal):
cd frontend && pnpm dev
```

## Scientific Acceptance Testing

The golden dataset tests in `backend/tests/scientific/` run the full pipeline with a known research case and assert that expected key targets and pathway terms appear in the results. This validates research-grade output against the literature.

To run scientific tests:
```bash
cd backend && uv run pytest tests/scientific/ -m scientific -v
```

Scientific tests are not run in normal CI — they require a seeded database with real KNApSAcK compound data and live external API access.

Reference: Mangul S, et al. Systematic benchmarking of omics computational tools. Nat Commun. 2019;10:1393.

## Test Architecture Decisions

### Backend mocking strategy

- **External HTTP** (ChEMBL, PubChem, STRING, UniProt, Open Targets, g:Profiler): patch `httpx.AsyncClient` via `unittest.mock.patch`. Use `AsyncMock` for `__aenter__`/`__aexit__`.
- **Database session**: pass a real SQLite in-memory session via pytest fixture (see `backend/tests/conftest.py`).
- **`with_retry`**: patch to a passthrough in unit tests to avoid sleep delays.
- **Stage orchestration**: inject fake stage functions via `patch("analysis.pipeline.STAGE_RUNNERS", {N: fake_fn})`.

### Frontend mocking strategy

- **API layer**: use MSW v2 (`frontend/tests/handlers.ts`) for integration tests. Use `vi.mock` for unit tests that don't need the full HTTP stack.
- **Cytoscape** (Stage 6, Stage 7 PPI graph): mock `react-cytoscapejs` in unit tests — jsdom has no canvas.
- **Router**: wrap components in `MemoryRouter` from `react-router-dom` for unit tests.
- **localStorage**: use `vi.stubGlobal('localStorage', ...)` or real localStorage with `afterEach(() => localStorage.clear())`.

### TDD workflow

New features and bug fixes follow Red-Green-Refactor:
1. Write a failing test that describes the desired behavior
2. Run it to confirm it fails (Red)
3. Implement the minimal fix
4. Run to confirm it passes (Green)
5. Refactor if needed, keeping tests green

## Coverage Targets

| Layer | Target | Rationale |
|---|---|---|
| `analysis/stages/` | ≥90% | Core scientific algorithms — errors here affect research validity |
| `integrations/` | ≥80% | External API clients — error paths must be tested |
| `app/routers/` | ≥80% | All HTTP endpoints must have at least one integration test |
| `app/repositories/` | ≥80% | ORM queries — dedup and upsert logic must be verified |
| Frontend components | ≥70% | UI components tested via render + interaction |
| Frontend hooks | ≥80% | State management hooks — success and error paths both covered |

## Known Limitations

- **Stage 6 / Stage 7 Cytoscape rendering**: canvas not available in jsdom. Unit tests mock the Cytoscape component. Visual rendering is only verified by the manual end-to-end proof against a running stack.
- **End-to-end flows**: full pipeline runs and stage-result rendering require a running backend + database and are verified manually, not by an automated frontend test in CI.
- **Scientific tests**: require live external APIs (PubChem, STRING, UniProt) and a fully seeded database. Run manually before major releases.

### Stage 3 — Target Identification

- **Human-only (9606) is a fixed-scope limitation.** All target resolution (UniProt client, ChEMBL
  client, PubChem BioAssay client, Stage-3 resolution) filters to `organism_id:9606` internally.
  A non-human UniProt accession is skipped and never persisted. This is not a user-tunable
  parameter — `human_only` was deliberately removed from the contract's `target` param block.
- **ChEMBL is load-bearing; PubChem BioAssay is supplementary.** If ChEMBL is unreachable, Stage 3
  raises `ServiceUnavailableError` (503) and the stage fails. If PubChem BioAssay is unreachable,
  it degrades to an empty result (`[]`) and Stage 3 continues with ChEMBL data only.
- **Manual targets are run-scoped (no edge).** Both ways of adding a target by hand at Step 3 —
  the plain add control and the SwissTargetPrediction (STP) paste-back — go through the same edit
  path (`POST /analyses/{id}/stages/3/edit`, after resolving accessions via `POST /targets/validate`).
  The target joins the stage's effective set and the **Target entity** persists as a canonical row,
  but **no `compound_targets` edge is written** — a user-asserted/predicted link must never be
  canonical (B4). There is no STP import endpoint.
- **Edge precedence (measured edges only):** `chembl_bioactivity` > `pubchem_bioassay`. A measured
  upsert never downgrades to a lower-precedence method. The `stp_import` value is legacy — the DB
  CHECK still permits it, but no code writes it (STP is run-scoped; see above).

### Stage 4 — Disease Target Collection

- **Open Targets is an ETL-time source, not a live call.** Stage 4 reads the ETL-seeded
  `disease_targets` snapshot (filtered by `min_score`, joined to `targets`, ordered by score) —
  analogous to KNApSAcK on the compound side. A **live / dynamic disease-target fetch is future
  work** (D1); the current stage is a database read of what the ETL loaded.
- **Seeded diseases only; non-seeded diseases use the manual path.** A disease with no seeded
  `disease_targets` rows yields an empty stage; targets are then added through the manual
  disease-target path (`POST /analyses/{id}/stages/4/edit`, resolved via `POST /targets/validate`).
  This is weak-but-valid — Stage 4 proceeds to its approval checkpoint with a count-0 honesty note
  rather than hard-stopping (the only unconditional hard-stop is Stage 5, zero overlap).
- **Overall association score only.** Datatype-filtered evidence scope (e.g. restricting to genetic
  or known-drug evidence) is **not supported** (D2) — Stage 4 reads the single overall association
  score the ETL seeded (`association_type = open_targets_overall`).
- **Manual disease-targets carry no association score** (D3) and write **no `disease_targets`
  edge**: the manual path persists the **Target** entity (canonical row) but the disease→target
  link is run-scoped only (Software Lock §6.2-E).
- **Human-only (9606) is fixed.** Stage 4 collects human targets only; this is not a tunable
  parameter.
