# Herbaflow Frontend

React 18 + TypeScript SPA for the Herbaflow network pharmacology platform. Provides a
UI for the 8-stage drug-discovery pipeline — compound selection, ADME screening, target
identification, disease association, PPI network visualization, hub gene ranking, and
pathway enrichment.

## Stack

| Layer | Library |
|---|---|
| UI framework | React 18 + TypeScript 5 + Vite 6 |
| Routing | React Router v7 |
| Server state | TanStack Query v5 (polling, cache invalidation) |
| Styling | Tailwind CSS v3 — `hf-*` design tokens only |
| Components | shadcn/ui (Radix primitives) |
| Network viz | Cytoscape.js + cytoscape-fcose |
| Charts | Recharts |
| Unit / integration tests | Vitest + React Testing Library + MSW v2 |
| E2E tests | Playwright |

## Dev Commands

```bash
pnpm dev                        # Start dev server at http://localhost:5173
pnpm build                      # TypeScript check + Vite production build
pnpm test                       # Vitest unit + integration tests (watch mode)
pnpm test:run                   # Vitest run (CI)
pnpm test:coverage              # Coverage report
pnpm exec playwright install    # First-time browser install (run once)
pnpm exec playwright test       # E2E tests (requires backend at localhost:8000)
```

## Architecture

| Path | Contents |
|---|---|
| `src/pages/` | `LandingPage`, `AboutPage`, `SetupPage`, `PipelinePage` |
| `src/components/shared/` | `StatCard`, `DataTable`, `StatusBadge`, `ExportButton`, `StageHeader`, `ApprovalBar`, `EmptyState`, `ErrorState` |
| `src/components/stages/` | `Stage1Panel` – `Stage8Panel` |
| `src/components/setup/` | `PlantSelector`, `DiseaseSelector`, `ModeToggle`, `AdvancedParameters` |
| `src/components/pipeline/` | `PipelineSidebar`, `StageNavItem` |
| `src/hooks/` | TanStack Query hooks (`useAnalysisStatus`, `usePlants`, `useDiseases`, etc.) |
| `src/types/api.ts` | TypeScript types matching all backend schemas |
| `src/lib/api.ts` | Typed fetch wrappers; base URL from `VITE_API_URL` |
| `src/mocks/` | MSW handlers and fixtures for Vitest |
| `tests/unit/` | Unit tests for shared components and hooks |
| `tests/integration/` | Integration tests for setup and pipeline flows |
| `e2e/` | Playwright end-to-end specs |

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |

## Key Notes

- Design tokens: use `hf-*` Tailwind classes only — never raw hex or Tailwind defaults (`gray-*`, `white`)
- `hf-sage` and `hf-terracotta` are data-visualization tokens — not for buttons or nav
- Stage panel data must always be null-guarded: `const result = analysis?.stage_results[String(n)] as StageNResult | null | undefined`
- Polling uses TanStack Query `refetchInterval` + `enabled: !isTerminalStatus(...)` — never poll manually
- E2E tests require the backend server running at `localhost:8000` and Playwright browsers installed

See `CLAUDE.md` for the full developer reference (conventions, constraints, adding a stage panel).
