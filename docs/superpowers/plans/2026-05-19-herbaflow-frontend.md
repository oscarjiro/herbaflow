# Herbaflow Frontend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the full Herbaflow React frontend — Landing, About, Setup form, and 8-stage analysis pipeline view — against the existing FastAPI backend.

**Architecture:** React 18 + TypeScript SPA built with Vite 6. Tailwind CSS v3 (design tokens from `design-system/colors_and_type.css` mapped into `tailwind.config.ts`). shadcn/ui for Radix primitives. TanStack Query v5 for all server state including 2 s polling. React Router v6 for 4 routes. No global state beyond TanStack Query cache + `localStorage` key `hf_last_analysis_id`.

**Tech Stack:** React 18, TypeScript 5, Vite 6, Tailwind CSS v3, shadcn/ui (latest), TanStack Query v5, React Router v6, Cytoscape.js + cytoscape-fcose, Recharts, Vitest + React Testing Library, MSW v2, Playwright

**Spec:** `docs/superpowers/specs/2026-05-19-herbaflow-frontend-design.md` — read it before every task.

---

## File Map

```
frontend/
  index.html
  vite.config.ts
  tailwind.config.ts          ← hf tokens mapped here
  tsconfig.json / tsconfig.app.json / tsconfig.node.json
  components.json             ← shadcn config
  vitest.config.ts
  playwright.config.ts
  src/
    main.tsx
    App.tsx                   ← router + QueryClientProvider
    index.css                 ← shadcn vars → hf tokens + Tailwind directives
    vite-env.d.ts
    types/
      api.ts                  ← all backend TypeScript types
    lib/
      api.ts                  ← typed fetch wrappers
      queryClient.ts
      utils.ts                ← cn() helper
    hooks/
      usePlants.ts
      useDiseases.ts
      useStartAnalysis.ts
      useAnalysis.ts
      useAnalysisStatus.ts
      useApproveStage.ts
      useRejectStage.ts
      useExportStage.ts
    components/
      ui/                     ← shadcn primitives (auto-generated, do not edit)
      shared/
        StatCard.tsx
        DataTable.tsx
        StatusBadge.tsx
        ExportButton.tsx
        StageHeader.tsx
        ApprovalBar.tsx
        EmptyState.tsx
        ErrorState.tsx
      pipeline/
        PipelineSidebar.tsx
        StageNavItem.tsx
      setup/
        PlantSelector.tsx
        DiseaseSelector.tsx
        ModeToggle.tsx
        AdvancedParameters.tsx
      stages/
        Stage1Panel.tsx  Stage2Panel.tsx  Stage3Panel.tsx  Stage4Panel.tsx
        Stage5Panel.tsx  Stage6Panel.tsx  Stage7Panel.tsx  Stage8Panel.tsx
      layout/
        NavBar.tsx
        Layout.tsx
    pages/
      LandingPage.tsx
      AboutPage.tsx
      SetupPage.tsx
      PipelinePage.tsx
    mocks/
      handlers.ts             ← MSW request handlers
      node.ts                 ← MSW server for Vitest
      data.ts                 ← fixture data
  tests/
    unit/
      StatCard.test.tsx
      DataTable.test.tsx
      StatusBadge.test.tsx
      useAnalysisStatus.test.ts
    integration/
      setup-flow.test.tsx
      pipeline-guided.test.tsx
      pipeline-auto.test.tsx
      pipeline-error.test.tsx
  e2e/
    landing.spec.ts
    setup-to-pipeline.spec.ts
    guided-pipeline.spec.ts
    auto-pipeline.spec.ts
    cache-restore.spec.ts
  CLAUDE.md
```

---

## Phase 0 — Backend Fixes

### Task 0: Fix CSV export + suppress unpopulated TargetRanking score fields

**Files:** `backend/app/routers/analyses.py`, `backend/tests/`

- [ ] Add CSV serialization for stages 1–6, 8 in the export endpoint (stage 7 already works)
- [ ] Exclude `disease_association_score`, `compound_support_score`, `final_score` from `TargetRanking` API responses (these are always null — set `exclude_none=True` on the Pydantic response model or use `response_model_exclude_none=True` on the route)
- [ ] Run `uv run pytest` — all 60 tests pass
- [ ] Update `backend/CLAUDE.md` and `docs/` to reflect CSV support added
- [ ] Commit: `fix(backend): add CSV export for stages 1-6,8; exclude null TargetRanking score fields`

---

## Phase 1 — Scaffold

### Task 1: Create Vite project and install dependencies

**Files:** `frontend/package.json`, `frontend/vite.config.ts`, `frontend/tsconfig*.json`

- [ ] Scaffold from `frontend/` directory:
```bash
cd frontend
npm create vite@latest . -- --template react-ts
```
- [ ] Install production dependencies:
```bash
npm install react-router-dom @tanstack/react-query @tanstack/react-query-devtools \
  cytoscape react-cytoscapejs cytoscape-fcose recharts \
  class-variance-authority clsx tailwind-merge \
  lucide-react
```
- [ ] Install dev dependencies:
```bash
npm install -D tailwindcss@3 postcss autoprefixer \
  @types/cytoscape \
  vitest @vitest/coverage-v8 jsdom \
  @testing-library/react @testing-library/jest-dom @testing-library/user-event \
  msw \
  @playwright/test
```
- [ ] Initialize Tailwind: `npx tailwindcss init -p`
- [ ] Run `npm run dev` — blank React app loads at `http://localhost:5173`
- [ ] Commit: `chore(frontend): scaffold Vite + React TS project with dependencies`

---

### Task 2: Configure Tailwind + map design tokens

**Files:** `frontend/tailwind.config.ts`

Map all `--hf-*` tokens from `design-system/colors_and_type.css` into Tailwind's `extend`. Non-obvious part — exact token structure:

```typescript
// frontend/tailwind.config.ts
import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        hf: {
          bg:           'var(--hf-bg)',
          surface:      'var(--hf-surface)',
          'surface-2':  'var(--hf-surface-2)',
          border:       'var(--hf-border)',
          'border-strong': 'var(--hf-border-strong)',
          fg1:          'var(--hf-fg-1)',
          fg2:          'var(--hf-fg-2)',
          fg3:          'var(--hf-fg-3)',
          fg4:          'var(--hf-fg-4)',
          sage:         'var(--hf-sage)',
          'sage-deep':  'var(--hf-sage-deep)',
          'sage-soft':  'var(--hf-sage-soft)',
          'sage-faint': 'var(--hf-sage-faint)',
          terracotta:   'var(--hf-terracotta)',
          'terracotta-soft': 'var(--hf-terracotta-soft)',
          success:      'var(--hf-success)',
          'success-soft': 'var(--hf-success-soft)',
          warning:      'var(--hf-warning)',
          'warning-soft': 'var(--hf-warning-soft)',
          danger:       'var(--hf-danger)',
          'danger-soft': 'var(--hf-danger-soft)',
          info:         'var(--hf-info)',
          'info-soft':  'var(--hf-info-soft)',
          n50:  '#F7F5F2', n100: '#EFEBE4', n200: '#E5E0D8',
          n300: '#D4CEC4', n500: '#9A958C', n600: '#6E6A62',
          n700: '#4A463F', n900: '#1A1A1A',
        },
      },
      fontFamily: {
        display: ['Instrument Serif', 'Georgia', 'serif'],
        sans:    ['Be Vietnam Pro', 'sans-serif'],
        mono:    ['Space Mono', 'monospace'],
      },
      borderRadius: {
        none: '0', sm: '2px', DEFAULT: '4px', md: '4px', lg: '8px', full: '9999px',
      },
    },
  },
  plugins: [],
} satisfies Config
```

- [ ] Verify: add `<div className="bg-hf-bg text-hf-fg1">test</div>` in App.tsx, confirm it renders with correct colours
- [ ] Commit: `chore(frontend): map hf design tokens into Tailwind config`

---

### Task 3: Configure shadcn/ui and src/index.css

**Files:** `frontend/components.json`, `frontend/src/index.css`

- [ ] Init shadcn (select Vite, no RSC, no src/): `npx shadcn@latest init -t vite`
  - baseColor: neutral
  - cssVariables: yes
- [ ] Replace the generated shadcn variable block in `src/index.css` with mappings to hf tokens:

```css
/* src/index.css */
@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Be+Vietnam+Pro:wght@300;400;500;600;700&family=Space+Mono:wght@400;700&display=swap');
@tailwind base;
@tailwind components;
@tailwind utilities;

/* Import design system tokens */
@import '../../design-system/colors_and_type.css';
@import '../../design-system/components.css';

@layer base {
  :root {
    /* Map shadcn/ui CSS vars → hf tokens */
    --background:    var(--hf-bg);
    --foreground:    var(--hf-fg-1);
    --card:          var(--hf-surface);
    --card-foreground: var(--hf-fg-1);
    --popover:       var(--hf-surface);
    --popover-foreground: var(--hf-fg-1);
    --primary:       var(--hf-neutral-900);
    --primary-foreground: #ffffff;
    --secondary:     var(--hf-neutral-100);
    --secondary-foreground: var(--hf-fg-1);
    --muted:         var(--hf-neutral-100);
    --muted-foreground: var(--hf-fg-3);
    --accent:        var(--hf-neutral-100);
    --accent-foreground: var(--hf-fg-1);
    --destructive:   var(--hf-danger);
    --destructive-foreground: #ffffff;
    --border:        var(--hf-border);
    --input:         var(--hf-border);
    --ring:          var(--hf-fg-1);
    --radius:        4px;
  }

  * { @apply border-border; }
  body {
    @apply bg-hf-bg text-hf-fg1 font-sans;
    font-size: var(--text-base);
  }
}
```

- [ ] Add shadcn components used throughout:
```bash
npx shadcn@latest add button input select badge table accordion tabs tooltip
```
- [ ] Commit: `chore(frontend): configure shadcn/ui with hf design tokens`

---

### Task 4: Vitest + MSW + Playwright setup

**Files:** `frontend/vitest.config.ts`, `frontend/src/mocks/node.ts`, `frontend/src/mocks/handlers.ts`, `frontend/src/mocks/data.ts`, `frontend/playwright.config.ts`

- [ ] Create `vitest.config.ts`:
```typescript
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/mocks/vitest.setup.ts'],
  },
})
```
- [ ] Create `src/mocks/vitest.setup.ts`:
```typescript
import '@testing-library/jest-dom'
import { beforeAll, afterEach, afterAll } from 'vitest'
import { server } from './node'

beforeAll(() => server.listen())
afterEach(() => server.resetHandlers())
afterAll(() => server.close())
```
- [ ] Create `src/mocks/node.ts`:
```typescript
import { setupServer } from 'msw/node'
import { handlers } from './handlers'
export const server = setupServer(...handlers)
```
- [ ] Create `src/mocks/handlers.ts` — stub happy-path handlers for all endpoints:
```typescript
import { http, HttpResponse } from 'msw'
import { plantsFixture, diseasesFixture, analysisFixture, statusFixture } from './data'

export const handlers = [
  http.get('/plants',   () => HttpResponse.json(plantsFixture)),
  http.get('/diseases', () => HttpResponse.json(diseasesFixture)),
  http.post('/analyses', () => HttpResponse.json({ analysis_id: 'test-id-1' }, { status: 201 })),
  http.get('/analyses/:id',        () => HttpResponse.json(analysisFixture)),
  http.get('/analyses/:id/status', () => HttpResponse.json(statusFixture)),
  http.post('/analyses/:id/approve', () => new HttpResponse(null, { status: 200 })),
  http.post('/analyses/:id/reject',  () => new HttpResponse(null, { status: 200 })),
  http.delete('/analyses/:id',       () => new HttpResponse(null, { status: 204 })),
]
```
- [ ] Create `src/mocks/data.ts` — fixture objects matching each schema in `types/api.ts` (write once, reuse across tests)
- [ ] Create `playwright.config.ts` pointing at `http://localhost:5173`, configure `webServer` to run `npm run dev`
- [ ] Run `npm run test` — 0 tests, no errors
- [ ] Commit: `chore(frontend): add Vitest + MSW v2 + Playwright test infrastructure`

---

## Phase 2 — Data Layer

### Task 5: TypeScript types

**File:** `frontend/src/types/api.ts`

- [ ] Define all types matching backend schemas (read `backend/app/schemas/` for exact field names):
  - `Plant`, `Disease`
  - `AnalysisMode = 'guided' | 'auto'`
  - `AnalysisStatus` (string union covering all state machine states)
  - `CreateAnalysisRequest`, `AnalysisStatusResponse`, `AnalysisRunResponse`
  - Stage result types: `Stage1Result`, `Stage2Result`, `Stage3Result`, `Stage4Result`, `Stage5Result`, `Stage6Result`, `Stage7Result`, `Stage8Result`
  - `CompoundResult`, `TargetResult`, `DiseaseTargetResult`, `HubGeneResult`, `PathwayTerm`
- [ ] Key non-obvious: `stage_results` on `AnalysisRunResponse` is `Record<string, unknown>` with typed accessors
- [ ] Export a `isTerminalStatus(s: string): boolean` helper: `return /complete$|failed$|rejected$/.test(s)`
- [ ] Commit: `feat(frontend): add TypeScript types for all backend schemas`

### Task 6: API client + QueryClient

**Files:** `frontend/src/lib/api.ts`, `frontend/src/lib/queryClient.ts`, `frontend/src/lib/utils.ts`

- [ ] `utils.ts` — standard shadcn cn() helper:
```typescript
import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'
export function cn(...inputs: ClassValue[]) { return twMerge(clsx(inputs)) }
```
- [ ] `api.ts` — typed fetch wrappers, base URL from `VITE_API_URL` env var (default `http://localhost:8000`). Export an `api` object with: `getPlants`, `getDiseases`, `createAnalysis`, `getAnalysis`, `getAnalysisStatus`, `approveStage`, `rejectStage`, `deleteAnalysis`, `exportStage` (returns raw `Response` for download)
- [ ] `queryClient.ts`:
```typescript
import { QueryClient } from '@tanstack/react-query'
export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000, retry: 1 } },
})
```
- [ ] Commit: `feat(frontend): add API client and QueryClient`

### Task 7: TanStack Query hooks

**Files:** `frontend/src/hooks/*.ts`

- [ ] `usePlants.ts`, `useDiseases.ts` — basic `useQuery` wrappers
- [ ] `useStartAnalysis.ts` — `useMutation`, on success: save `analysis_id` to localStorage, navigate to `/analysis/:id`
- [ ] `useAnalysis.ts` — `useQuery(['analysis', id], () => api.getAnalysis(id))`
- [ ] Non-obvious — `useAnalysisStatus.ts` with conditional polling:
```typescript
import { useQuery } from '@tanstack/react-query'
import { api } from '@/lib/api'
import { isTerminalStatus } from '@/types/api'

export function useAnalysisStatus(id: string) {
  return useQuery({
    queryKey: ['analysis', id, 'status'],
    queryFn: () => api.getAnalysisStatus(id),
    refetchInterval: (query) => {
      const status = query.state.data?.status
      if (!status || isTerminalStatus(status)) return false
      return 2000
    },
    refetchIntervalInBackground: false,
  })
}
```
- [ ] `useApproveStage.ts`, `useRejectStage.ts` — `useMutation`, on success: `queryClient.invalidateQueries(['analysis', id])`
- [ ] `useExportStage.ts` — calls `api.exportStage`, gets blob, triggers browser download via `URL.createObjectURL`
- [ ] Write unit test `tests/unit/useAnalysisStatus.test.ts` — verify polling stops when status is `complete`, `failed`, `stage_3_rejected`
- [ ] Commit: `feat(frontend): add TanStack Query hooks with polling logic`

---

## Phase 3 — Shared Components

### Task 8: Shared components

**Files:** `frontend/src/components/shared/*.tsx`

Implement all of: `StatCard`, `StatusBadge`, `EmptyState`, `ErrorState`, `StageHeader`, `ApprovalBar`, `ExportButton`. Follow component designs in spec exactly.

Key notes:
- `StatusBadge` maps status string → colour: running=info, awaiting_approval=warning, complete=success, failed/rejected=danger
- `ApprovalBar` renders Approve + Reject buttons; only shown in guided mode when stage is `awaiting_approval`
- All colours from hf tokens — no raw hex
- Radii: buttons 2px (`rounded-sm`), badges 4px (`rounded`), cards 8px (`rounded-lg`)

- [ ] Write `tests/unit/StatCard.test.tsx` + `StatusBadge.test.tsx`
- [ ] Commit: `feat(frontend): add shared components`

### Task 9: DataTable component

**File:** `frontend/src/components/shared/DataTable.tsx`

Generic sortable + filterable table component. Non-trivial — implement:
- Column config: `{ key, header, sortable?, render? }`
- Sort state (column + direction), filter string
- Uses shadcn `<Table>` primitives
- Pagination: show first 50 rows, "Show all" toggle

- [ ] Write `tests/unit/DataTable.test.tsx` — verify sort, filter
- [ ] Commit: `feat(frontend): add DataTable component with sort and filter`

---

## Phase 4 — Layout + Static Pages

### Task 10: Layout, NavBar, App.tsx routing

**Files:** `frontend/src/components/layout/NavBar.tsx`, `Layout.tsx`, `src/App.tsx`, `src/main.tsx`

- [ ] `NavBar.tsx` — Herbaflow wordmark (Instrument Serif) + About link
- [ ] `Layout.tsx` — wraps children in `min-h-screen bg-hf-bg`, renders NavBar above
- [ ] `App.tsx`:
```tsx
import { QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { queryClient } from '@/lib/queryClient'
import Layout from '@/components/layout/Layout'
import LandingPage from '@/pages/LandingPage'
import SetupPage from '@/pages/SetupPage'
import PipelinePage from '@/pages/PipelinePage'
import AboutPage from '@/pages/AboutPage'

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<LandingPage />} />
            <Route path="analysis" element={<SetupPage />} />
            <Route path="analysis/:id" element={<PipelinePage />} />
            <Route path="about" element={<AboutPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  )
}
```
- [ ] `main.tsx` — render `<App />` into `#root`
- [ ] Commit: `feat(frontend): add routing, layout, and NavBar`

### Task 11: LandingPage + AboutPage

**Files:** `frontend/src/pages/LandingPage.tsx`, `AboutPage.tsx`

- [ ] `LandingPage` — hero with `<ascii-dna>` web component (load from `design-system/assets/ascii-dna.js` via `<script>` in `index.html`), one-paragraph description, "Start Analysis" CTA → `/analysis`
- [ ] `AboutPage` — static content: project description, methodology, author info, PDF placeholder ("Coming soon")
- [ ] Commit: `feat(frontend): add Landing and About pages`

---

## Phase 5 — Setup Page

### Task 12: Setup form components

**Files:** `frontend/src/components/setup/*.tsx`

- [ ] `PlantSelector.tsx` — combobox multi-select backed by `usePlants()`. Shows scientific name + family + compound count. Uses shadcn Command + Popover primitives.
- [ ] `DiseaseSelector.tsx` — same pattern, single-select, backed by `useDiseases()`
- [ ] `ModeToggle.tsx` — Guided (default) / Auto radio/toggle
- [ ] `AdvancedParameters.tsx` — shadcn Accordion (collapsed by default). Groups params by stage per spec table. Number inputs with default values shown as placeholders. Full param list in spec §Setup Form.
- [ ] Commit: `feat(frontend): add setup form components`

### Task 13: SetupPage

**File:** `frontend/src/pages/SetupPage.tsx`

- [ ] On mount: check `localStorage.getItem('hf_last_analysis_id')`. If set, fetch status — if not failed/rejected, redirect to `/analysis/:id`
- [ ] Form: analysis name (auto-default like `Andrographis × T2D — 2026-05-19`), PlantSelector, DiseaseSelector, ModeToggle, AdvancedParameters
- [ ] Submit → `useStartAnalysis()` mutation → POST `/analyses`
- [ ] Write `tests/integration/setup-flow.test.tsx` — renders form, fills plant/disease, submits, asserts redirect to `/analysis/test-id-1`
- [ ] Commit: `feat(frontend): add Setup page with localStorage cache restore`

---

## Phase 6 — Pipeline Page

### Task 14: PipelineSidebar + StageNavItem

**Files:** `frontend/src/components/pipeline/PipelineSidebar.tsx`, `StageNavItem.tsx`

- [ ] Sidebar: 220px fixed width, `bg-hf-surface-2`, analysis name + mode badge at top
- [ ] 8 `StageNavItem` components. State → visual mapping:
  - completed: checkmark, muted text, clickable
  - running: spinner (animated), bold
  - awaiting_approval: pulsing dot, bold — action required
  - future: dimmed, not clickable
- [ ] "New Analysis" link at bottom: navigates to `/analysis` + clears `hf_last_analysis_id`
- [ ] Collapses to hamburger toggle at `< 768px`
- [ ] Commit: `feat(frontend): add PipelineSidebar and StageNavItem`

### Task 15: PipelinePage + StagePanelRouter

**File:** `frontend/src/pages/PipelinePage.tsx`

Non-obvious wiring of polling + selected stage panel:

```tsx
export default function PipelinePage() {
  const { id } = useParams<{ id: string }>()
  const [activeStage, setActiveStage] = useState<number | null>(null)
  const { data: status } = useAnalysisStatus(id!)
  const { data: analysis } = useAnalysis(id!)

  // When status advances, auto-focus the current stage
  useEffect(() => {
    if (status?.current_stage) setActiveStage(status.current_stage)
  }, [status?.current_stage])

  // Error state
  if (status?.status === 'failed') return <ErrorState message={status.error_message} />

  return (
    <div className="flex h-screen">
      <PipelineSidebar
        status={status}
        analysis={analysis}
        activeStage={activeStage}
        onStageClick={setActiveStage}
      />
      <main className="flex-1 overflow-y-auto p-6">
        <StagePanelRouter
          stage={activeStage}
          analysis={analysis}
          status={status}
          analysisId={id!}
        />
      </main>
    </div>
  )
}
```

- [ ] `StagePanelRouter` — switch on `stage` 1–8, render corresponding panel. Shows `EmptyState` if stage result not yet available.
- [ ] Write `tests/integration/pipeline-guided.test.tsx` — mock status progression, assert Approve/Reject buttons appear, clicking Approve calls POST endpoint
- [ ] Write `tests/integration/pipeline-auto.test.tsx` — mock auto mode status → complete, assert no approval buttons
- [ ] Write `tests/integration/pipeline-error.test.tsx` — mock `failed` status, assert ErrorState shown
- [ ] Commit: `feat(frontend): add PipelinePage with polling, stage routing, and approval flow`

---

## Phase 7 — Stage Panels 1–5

### Task 16: Stage panels 1, 2, 3, 4

**Files:** `Stage1Panel.tsx` through `Stage4Panel.tsx`

All follow the same pattern: receive `result: StageNResult`, render via `StatCard` + `DataTable` + `StageHeader`. Follow spec §Stage Panel Designs exactly.

Key notes:
- Stage 2: stats bar uses hf-success-soft / hf-danger-soft / hf-warning-soft backgrounds; compound table is filterable by pass/fail
- Stage 3: gene tags scrollable, first 20 visible + "show all" toggle
- Stage 4: source badge (DB cache vs API) uses StatusBadge

- [ ] Commit: `feat(frontend): add Stage 1–4 panels`

### Task 17: Stage 5 — SVG Venn diagram

**File:** `frontend/src/components/stages/Stage5Panel.tsx`

Non-obvious — hand-rolled SVG Venn. No external lib needed:

```tsx
function VennDiagram({ compoundOnly, overlap, diseaseOnly }: VennProps) {
  const W = 280, H = 160, r = 70, offset = 45
  const cx1 = W / 2 - offset / 2
  const cx2 = W / 2 + offset / 2
  const cy  = H / 2
  return (
    <svg width={W} height={H} className="mx-auto">
      <circle cx={cx1} cy={cy} r={r} fill="var(--hf-sage-soft)"   opacity={0.7} />
      <circle cx={cx2} cy={cy} r={r} fill="var(--hf-info-soft)"   opacity={0.7} />
      <text x={cx1 - offset} y={cy} textAnchor="middle" fontSize={12}>{compoundOnly}</text>
      <text x={W / 2}         y={cy} textAnchor="middle" fontSize={12} fontWeight={600}>{overlap}</text>
      <text x={cx2 + offset} y={cy} textAnchor="middle" fontSize={12}>{diseaseOnly}</text>
    </svg>
  )
}
```

- [ ] Below diagram: stats row with Jaccard index, p-value, significance badge; overlap gene list
- [ ] Commit: `feat(frontend): add Stage 5 SVG Venn diagram panel`

---

## Phase 8 — Stage Panels 6–8

### Task 18: Stage 6 — Cytoscape.js PPI network

**File:** `frontend/src/components/stages/Stage6Panel.tsx`

Non-obvious setup:

```bash
npm install -D @types/cytoscape   # types only; cytoscape + react-cytoscapejs installed in Task 1
```

```tsx
import CytoscapeComponent from 'react-cytoscapejs'
import fcose from 'cytoscape-fcose'
import Cytoscape from 'cytoscape'
Cytoscape.use(fcose)

// Node colour by type
const styleSheet = [
  { selector: 'node[type="hub"]',     style: { 'background-color': 'var(--hf-sage)' } },
  { selector: 'node[type="overlap"]', style: { 'background-color': 'var(--hf-fg-1)' } },
  { selector: 'node[type="other"]',   style: { 'background-color': 'var(--hf-fg-4)' } },
  { selector: 'edge',                 style: { width: 'data(weight)', 'line-color': 'var(--hf-border-strong)' } },
]
```

- Backend already returns Cytoscape.js format (`nodes` + `edges` arrays)
- Edge `weight` = `combined_score` scaled to `1–6`
- Controls: layout toggle (fcose / grid / circle), fit-to-screen button, export PNG via `cy.png()`
- Hover tooltip: gene symbol + degree centrality via `mouseover` event
- Click: highlight neighbourhood (`cy.$('node').removeClass('dimmed'); node.neighborhood().removeClass('dimmed')`)
- Node / edge count stats above canvas
- [ ] Commit: `feat(frontend): add Stage 6 Cytoscape.js PPI network panel`

### Task 19: Stage 7 — Hub gene analysis

**File:** `frontend/src/components/stages/Stage7Panel.tsx`

- Ranking table via `DataTable`: rank, gene symbol, degree, betweenness, closeness, eigenvector, hub badge, hub+bottleneck badge
- Rows with `is_hub=true` get `bg-hf-sage-faint` row class
- Threshold footnote below table
- CSV export button via `useExportStage(id, 7, 'csv')` — this is the only stage with real CSV

- [ ] Commit: `feat(frontend): add Stage 7 hub gene analysis panel`

### Task 20: Stage 8 — Pathway enrichment

**File:** `frontend/src/components/stages/Stage8Panel.tsx`

Non-obvious Recharts setup:

```tsx
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts'

// x-axis = -log10(fdr), y-axis = term name (truncated to 40 chars)
const chartData = terms
  .slice(0, 20)
  .map(t => ({ name: t.term_name.slice(0, 40), value: -Math.log10(t.fdr) }))

<ResponsiveContainer width="100%" height={400}>
  <BarChart data={chartData} layout="vertical">
    <XAxis type="number" label={{ value: '-log₁₀(FDR)', position: 'insideBottom' }} />
    <YAxis type="category" dataKey="name" width={200} tick={{ fontSize: 11 }} />
    <Bar dataKey="value" fill="var(--hf-sage)" />
    <Tooltip
      formatter={(v: number, _n, { payload }) =>
        [`FDR: ${payload.fdr?.toExponential(2)}`, payload.term_name]}
    />
  </BarChart>
</ResponsiveContainer>
```

- 4 tabs (GO:BP, GO:MF, GO:CC, KEGG) via shadcn Tabs
- Total significant count badge in header
- [ ] Commit: `feat(frontend): add Stage 8 pathway enrichment panel with Recharts`

---

## Phase 9 — Tests

### Task 21: Unit tests

**Files:** `tests/unit/*.test.{tsx,ts}`

- [ ] `StatCard.test.tsx` — renders value + label correctly
- [ ] `DataTable.test.tsx` — sort toggles correctly, filter hides non-matching rows
- [ ] `StatusBadge.test.tsx` — correct colour class for each status category
- [ ] `useAnalysisStatus.test.ts` — polling stops on `complete`, `failed`, `stage_3_rejected`; continues on `stage_2_running`

Run: `npm run test -- tests/unit`

- [ ] Commit: `test(frontend): add unit tests for shared components and polling hook`

### Task 22: Integration tests (MSW)

**Files:** `tests/integration/*.test.tsx`

- [ ] `setup-flow.test.tsx` — full form submit → redirect
- [ ] `pipeline-guided.test.tsx` — mock status as `stage_3_awaiting_approval`, assert ApprovalBar renders; click Approve, assert POST called, status invalidated
- [ ] `pipeline-auto.test.tsx` — mock auto mode, status `complete`, assert no ApprovalBar
- [ ] `pipeline-error.test.tsx` — mock `failed` status, assert ErrorState

Override handlers per test with `server.use(http.get(...))` for error cases.

Run: `npm run test -- tests/integration`

- [ ] Commit: `test(frontend): add integration tests for setup and pipeline flows`

### Task 23: E2E tests (Playwright)

**Files:** `e2e/*.spec.ts`

Requires running backend + frontend. Run: `npx playwright test`

- [ ] `setup-to-pipeline.spec.ts` — select plants, select disease, submit, assert redirected to `/analysis/:id`
- [ ] `guided-pipeline.spec.ts` — walk all 8 stages, click Approve each time, assert `complete` state
- [ ] `auto-pipeline.spec.ts` — submit with auto mode, wait for complete
- [ ] `cache-restore.spec.ts` — set `hf_last_analysis_id` in localStorage, navigate to `/analysis`, assert redirect to pipeline page
- [ ] Commit: `test(frontend): add Playwright E2E tests`

---

## Phase 10 — Docs

### Task 24: frontend/CLAUDE.md + docs/frontend.md

**Files:** `frontend/CLAUDE.md`, `docs/frontend.md`

- [ ] `frontend/CLAUDE.md` — conventions: file structure, Tailwind token usage rules (sage/terracotta = data-viz only), test commands, how to add a shadcn component, polling behaviour notes
- [ ] `docs/frontend.md` — human-readable decisions + tradeoffs (for thesis), includes backend gap fixes made
- [ ] Final commit: `docs(frontend): add CLAUDE.md and frontend.md`

---

## Verification

After all tasks complete:

1. `npm run dev` — app loads, all 4 routes render without errors
2. `npm run test` — all unit + integration tests pass
3. `npx playwright test` — all 5 E2E journeys pass (requires backend running)
4. Full guided pipeline: submit → approve all 8 stages → reach `complete`
5. Full auto pipeline: submit → wait → reach `complete`
6. Rejection flow: reject stage → "Start New Analysis" CTA shown
7. Browser cache restore: reload mid-pipeline → redirected correctly
8. Export: Stage 7 CSV download works; JSON export works for all stages
