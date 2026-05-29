# Herbaflow Frontend

React 19 + TypeScript + Vite SPA for the 8-stage drug-discovery pipeline.

## Dev Commands

```bash
pnpm dev                        # Start dev server (port 5173)
pnpm build                      # TypeScript + Vite production build
pnpm test                       # Vitest unit + integration tests
pnpm exec playwright install    # First-time browser install (run once)
pnpm exec playwright test       # E2E tests (requires backend at localhost:8000)
```

## Architecture

| Path | Contents |
|---|---|
| `src/pages/` | `PipelinePage.tsx`, `SetupPage.tsx`, `DashboardPage.tsx` |
| `src/components/shared/` | `StatCard`, `DataTable`, `StatusBadge`, `ExportButton`, `StageHeader`, `ApprovalBar`, `EmptyState`, `ErrorState`, `StageSkeletonLoader`, `AddUserCompoundForm`, `AddTargetForm`, `SkippedStageNotice`, `DataSources`, `StageParamsPanel` |
| `src/components/stages/` | `Stage1Panel` – `Stage8Panel` |
| `src/components/setup/` | `PlantSelector`, `DiseaseSelector`, `ModeToggle`, `AdvancedParameters` |
| `src/components/pipeline/` | `PipelineSidebar`, `StageNavItem` |
| `src/hooks/` | TanStack Query hooks (`useAnalysisStatus`, `useAnalysis`, `useStartAnalysis`, `useApproveStage`, `useResetFromStage`, `useExportStage`, `usePlants`, `useDiseases`, `useAddUserCompound`, `useRemoveUserCompound`, `useAddUserTarget`, `useRemoveUserTarget`, `useAddUserDiseaseTarget`, `useRemoveUserDiseaseTarget`) |
| `src/types/api.ts` | TypeScript types matching backend schemas |
| `src/lib/api.ts` | Typed fetch wrappers; base URL from `VITE_API_URL` |
| `src/mocks/` | MSW fixtures for testing |

## Key Constraints

- **Stage result guards**: always cast `analysis?.stage_results[`stage_${n}`] as StageNResult | null | undefined` (keys are `stage_1`..`stage_8`) and guard `if (!result)` before rendering
- **Cytoscape listeners**: call `cy.removeAllListeners()` in effects to prevent duplicate registration
- **Cytoscape colors**: CSS vars only — `var(--hf-*)` — never raw hex values
- **FDR flooring**: clamp `-log10(FDR)` at minimum 1 — `t.fdr > 0 ? Math.max(1, -Math.log10(t.fdr)) : 1`
- **Tailwind**: `hf-*` tokens only; never raw colors or Tailwind defaults (`gray-*`, `white`, etc.)
- **`hf-sage`, `hf-terracotta`**: data-viz only (charts, legends, Cytoscape nodes) — not for buttons, nav, or interactive elements
- **Polling**: use `useAnalysisStatus` with `refetchInterval` + `enabled: !isTerminalStatus(...)` — never poll manually
- **Adding a stage panel**: create component → define types in `api.ts` → wire into `PipelinePage.tsx` `STAGE_COMPONENTS` map → add MSW fixture in `src/mocks/data.ts`
- **E2E tests**: require backend running at `localhost:8000` AND `pnpm exec playwright install` done once

## Never Do

- Never use `var(--primary-*)`, `var(--secondary-*)`, or `var(--muted-*)` in Cytoscape stylesheets
- Never hard-code hex colors anywhere
- Never poll manually — use TanStack Query `refetchInterval` + `enabled`
- Never skip the null-guard on stage panel result data

## Environment

| Variable | Default | Purpose |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Backend API base URL |
