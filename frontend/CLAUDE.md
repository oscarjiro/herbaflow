# Herbaflow Frontend — Developer Guide

React 18 + TypeScript + Vite SPA for the network pharmacology pipeline. Serves as the primary UI for the 8-stage drug discovery workflow.

## File Structure

```
src/
├── components/
│   ├── shared/          # Reusable UI elements
│   │   ├── StatCard.tsx
│   │   ├── DataTable.tsx
│   │   ├── StatusBadge.tsx
│   │   ├── ExportButton.tsx
│   │   ├── StageHeader.tsx
│   │   ├── ApprovalBar.tsx
│   │   ├── EmptyState.tsx
│   │   └── ErrorState.tsx
│   ├── stages/          # Stage1Panel – Stage8Panel
│   ├── pipeline/        # PipelineSidebar, StageNavItem
│   ├── setup/           # PlantSelector, DiseaseSelector, ModeToggle, AdvancedParameters
│   └── layout/          # NavBar, Layout
├── hooks/               # TanStack Query hooks
├── types/api.ts         # TypeScript types matching backend schemas
├── lib/api.ts           # Typed fetch wrappers; base URL from VITE_API_URL
├── mocks/               # MSW fixtures for testing
└── tests/               # Vitest + Playwright
```

## Tailwind Token Rules

**Use ONLY `hf-*` prefixed tokens:**
```tsx
// ✅ Correct
<div className="bg-hf-bg text-hf-fg1 border border-hf-border rounded-sm" />

// ❌ Wrong
<div className="bg-white text-black border border-gray-300" />
```

**Color semantics:**
- `hf-sage`, `hf-terracotta` → **data-viz only** (charts, legends, Cytoscape nodes)
- Never use for buttons, navigation, or interactive elements

**Radii:**
- Buttons: `rounded-sm`
- Badges/chips: `rounded`
- Cards: `rounded-lg`

**Cytoscape stylesheets:**
- Use CSS variables only: `var(--hf-sage)`, `var(--hf-primary)`
- No raw hex values

## Stage Panel Pattern

All stage panels (1–8) follow this structure:

```tsx
import { StageNResult } from '@/types/api'
import { StageHeader } from '@/components/shared/StageHeader'
import { EmptyState } from '@/components/shared/EmptyState'

export interface StageNPanelProps {
  stage: number
  analysis: AnalysisResponse | null
  status: AnalysisStatusResponse | null
  analysisId: string
}

export function StageNPanel({ stage, analysis, status, analysisId }: StageNPanelProps) {
  // Extract typed result from analysis.stage_results
  const result = analysis?.stage_results[String(stage)] as StageNResult | null | undefined
  
  if (!result) {
    return <EmptyState message="Stage N results not yet available" />
  }
  
  return (
    <div className="space-y-6">
      <StageHeader 
        stage={N} 
        name="Stage Name" 
        status={status?.status ?? 'complete'} 
        elapsedSeconds={null}
      />
      {/* Render stage-specific content */}
    </div>
  )
}
```

## Polling & Server State

Use `useAnalysisStatus` for all polling:

```tsx
const { data: status, isLoading, error } = useAnalysisStatus(analysisId, {
  refetchInterval: 2000, // auto-polls every 2s
  enabled: !isTerminalStatus(analysis?.status) // stops when complete/failed
})
```

Do not poll manually. TanStack Query handles cache invalidation, race conditions, and cleanup.

## Adding a shadcn Component

```bash
cd frontend
pnpm dlx shadcn@latest add <component-name>
```

This scaffolds the component into `src/components/ui/` with Radix primitives and Tailwind styling.

## Adding a New Stage Panel

1. **Create component** at `src/components/stages/StageNPanel.tsx` following the pattern above
2. **Define types** in `src/types/api.ts` (if not already present): `StageNResult`
3. **Add to routing** in `src/pages/PipelinePage.tsx`:
   ```tsx
   const STAGE_COMPONENTS: Record<number, React.ComponentType<StagePanelProps>> = {
     // ...
     N: StageNPanel
   }
   ```
4. **Add fixture data** to `src/mocks/data.ts` for `stage_results['N']`
5. **Verify TypeScript build**: `pnpm build`

## Test Commands

```bash
# Unit + integration tests (Vitest)
pnpm test

# Unit tests only
pnpm test -- tests/unit

# Integration tests only
pnpm test -- tests/integration

# E2E tests (requires backend + frontend running)
pnpm exec playwright test

# Production build (TypeScript + Vite)
pnpm build
```

## Environment Variables

| Variable        | Source      | Purpose                                  |
| --------------- | ----------- | ---------------------------------------- |
| `VITE_API_URL`  | `.env.local` | Backend API base URL (default: http://localhost:8000) |

Fetch wrappers in `src/lib/api.ts` automatically prepend this URL.

## Key Constraints

- **Stage result guards**: Always cast `analysis?.stage_results[String(n)]` with `as StageNResult | null | undefined` and guard with `if (!result)`
- **Cytoscape re-renders**: Call `cy.removeAllListeners()` in effects to avoid duplicate listener registration
- **FDR flooring**: Clamp `-log10(FDR)` at 1 to avoid Infinity values in Recharts
- **No polling race conditions**: TanStack Query's `refetchInterval` + `enabled` guard prevents stale state

## Dependencies

| Package              | Version | Purpose                         |
| -------------------- | ------- | ------------------------------- |
| React                | ^18     | UI framework                    |
| TypeScript           | ^5      | Type safety                     |
| Vite                 | ^6      | Build tool + HMR                |
| TanStack Query       | ^5      | Server state + polling          |
| Tailwind CSS         | ^3      | Styling + design system         |
| shadcn/ui           | latest  | Accessible Radix components     |
| Cytoscape.js         | ^3.28   | Graph visualization             |
| fcose                | ^2.2    | PPI network layout              |
| Recharts             | ^2.10   | Data visualization charts       |
| Vitest               | ^1      | Unit test runner                |
| Playwright           | ^1      | E2E testing                     |
| MSW                  | ^2      | API mocking for tests           |
