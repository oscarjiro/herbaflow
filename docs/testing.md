# HerbaFlow Testing Methodology

## Test Types

| Type | Tool | Location | Coverage target |
|---|---|---|---|
| Unit (backend) | pytest | `backend/tests/unit/` | ≥80% business logic |
| Integration (backend) | pytest | `backend/tests/integration/` | All API endpoints |
| Unit (frontend) | Vitest | `frontend/tests/unit/` | ≥80% components/hooks |
| Integration (frontend) | Vitest + MSW | `frontend/tests/integration/` | Pipeline flows |
| E2E | Playwright | `frontend/tests/e2e/` | Critical user journeys |
| Scientific acceptance | pytest | `backend/tests/scientific/` | Full pipeline with reference data |

## Running Tests

### Backend unit tests
```bash
cd backend && uv run pytest tests/unit/ -v
```

### Backend with coverage
```bash
cd backend && uv run pytest --cov=analysis --cov=app --cov=integrations --cov-report=term-missing -q
```

### Frontend unit tests
```bash
cd frontend && pnpm test:run
```

### Frontend with coverage
```bash
cd frontend && pnpm test:coverage
```

### E2E (requires running stack)
```bash
# Start backend (separate terminal):
cd backend && uv run uvicorn app.main:app --reload

# Start frontend dev server (separate terminal):
cd frontend && pnpm dev

# Run E2E tests:
cd frontend && pnpm test:e2e

# For fixture-based tests, set the completed analysis ID:
COMPLETED_ANALYSIS_ID=<uuid> pnpm test:e2e tests/e2e/stage-results-visible.spec.ts
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

- **API layer**: use MSW v2 (`frontend/src/mocks/handlers.ts`) for integration tests. Use `vi.mock` for unit tests that don't need the full HTTP stack.
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

- **Stage 6 / Stage 7 Cytoscape rendering**: canvas not available in jsdom. Unit tests mock the Cytoscape component. Visual rendering is only verified in E2E.
- **E2E tests without live stack**: `full-pipeline.spec.ts` and `stage-results-visible.spec.ts` require a running backend + database. They are not run in unit CI.
- **Scientific tests**: require live external APIs (PubChem, STRING, UniProt) and a fully seeded database. Run manually before major releases.

### Stage 3 — Target Identification

- **Human-only (9606) is a fixed-scope limitation.** All target resolution (UniProt client, ChEMBL
  client, PubChem BioAssay client, Stage-3 resolution) filters to `organism_id:9606` internally.
  A non-human UniProt accession is skipped and never persisted. This is not a user-tunable
  parameter — `human_only` was deliberately removed from the contract's `target` param block.
- **ChEMBL is load-bearing; PubChem BioAssay is supplementary.** If ChEMBL is unreachable, Stage 3
  raises `ServiceUnavailableError` (503) and the stage fails. If PubChem BioAssay is unreachable,
  it degrades to an empty result (`[]`) and Stage 3 continues with ChEMBL data only.
- **Two manual-target paths with different persistence.** (1) Plain add via the Step-3 edit
  control (`POST /analyses/{id}/stages/3/edit`) is run-scoped: the target is included in the
  stage's effective set but no `compound_targets` edge is written to the DB. (2) STP paste-back
  via `POST /analyses/{id}/import-stp-targets` writes real `compound_targets` edges with
  `prediction_method='stp_import'`. The difference is intentional: edit-layer additions are
  ephemeral curation; STP import is evidence with a source attribution.
- **Edge precedence:** `chembl_bioactivity` > `pubchem_bioassay` > `stp_import`. A measured
  upsert never downgrades to a lower-precedence method; STP import skips any pair that already
  has a measured edge (`skipped_measured` in the import response).
