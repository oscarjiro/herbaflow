# Herbaflow Frontend Design Spec

**Date:** 2026-05-19  
**Status:** Approved  
**Scope:** Full frontend implementation — Analysis pipeline UI, Landing, About

---

## Context

The Herbaflow backend is complete: a FastAPI 8-stage network pharmacology analysis pipeline with 60 passing tests. The frontend does not yet exist (`frontend/` is a placeholder). This spec defines the frontend architecture to ship before the thesis deadline.

Primary goal: a functional, academically presentable web UI for the network pharmacology pipeline. Design quality matters but pipeline completeness is the priority.

---

## Stack

| Tool                           | Purpose                                      |
| ------------------------------ | -------------------------------------------- |
| React 18 + TypeScript          | UI framework                                 |
| Vite                           | Build tool                                   |
| Tailwind CSS v3                | Utility styling (tokens from design system)  |
| shadcn/ui                      | Base component library (Radix UI primitives) |
| TanStack Query v5              | Server state, polling, mutations             |
| React Router v6                | Client-side routing                          |
| Cytoscape.js                   | PPI network visualization (Stage 6)          |
| Recharts                       | Enrichment bar charts (Stage 8)              |
| Vitest + React Testing Library | Unit + integration tests                     |
| MSW v2                         | API mocking for integration tests            |
| Playwright                     | E2E tests                                    |

---

## Design System Integration

Design tokens live in `design-system/colors_and_type.css` and `design-system/components.css`. These are the authoritative source.

**Integration strategy:**

- Map all `--hf-*` tokens into `tailwind.config.ts` under `extend.colors`, `extend.fontFamily`, `extend.spacing`, `extend.borderRadius`
- Map shadcn/ui CSS vars (`--background`, `--foreground`, `--primary`, etc.) to hf tokens in `src/index.css`
- Never hardcode hex values — reference tokens everywhere

**Visual rules to enforce:**

- Sage (`--hf-sage`) and terracotta (`--hf-terracotta`) reserved for data visualization only — not buttons, brand, or navigation
- Primary actions use ink (`--hf-fg-1` / `--hf-neutral-900`)
- Page background: `--hf-bg` (#F7F5F2, warm paper)
- Cards use `--hf-surface` (white) with 1px `--hf-border`
- Radii: 2px buttons, 4px chips/badges, 8px cards/panels
- Typography: Instrument Serif for display/headings, Be Vietnam Pro for UI

---

## Routing

```
/                  → Landing page
/analysis          → Setup form (new analysis)
/analysis/:id      → Pipeline view (sidebar + stage panel)
/about             → About page
```

**Browser cache restore:** On mount of `/analysis`, check `localStorage.getItem("hf_last_analysis_id")`. If set and analysis status is not `failed`/rejected, redirect to `/analysis/:id`.

On `POST /analyses` success: save `analysis_id` to localStorage, navigate to `/analysis/:id`.

---

## Pages

### Landing (`/`)

- Hero with `<ascii-dna>` web component (rotating helix, from `design-system/assets/ascii-dna.js`)
- One-paragraph description of Herbaflow (network pharmacology, Indonesian medicinal plants)
- "Start Analysis" CTA → `/analysis`
- Navigation bar: Herbaflow logo, About link

### About (`/about`)

- Project description, methodology overview (static content)
- Author info
- PDF user manual link (placeholder — "Coming soon")

### Setup Form (`/analysis`)

Full-page form. Sections:

1. **Analysis name** — text input, auto-generated default (e.g., `Andrographis × T2D — 2026-05-19`)
2. **Plant selection** — searchable multi-select, data from `GET /plants`, shows scientific name + family + compound count
3. **Disease selection** — searchable single-select, data from `GET /diseases`, shows name + ontology ID
4. **Mode** — radio/toggle: Guided (default) vs Auto
5. **Advanced parameters** — collapsed accordion, grouped by stage:

| Stage               | Params                                                                                                 | Defaults                          |
| ------------------- | ------------------------------------------------------------------------------------------------------ | --------------------------------- |
| ADME (2)            | max_mw, max_logp, max_hbd, max_hba, max_tpsa, max_rotatable_bonds, apply_veber, np_exception_threshold | 500, 5, 5, 10, 140, 10, true, 0.5 |
| Targets (3)         | min_pchembl, human_only                                                                                | 5.0, true                         |
| Disease targets (4) | min_score                                                                                              | 0.3                               |
| Network (6)         | min_confidence                                                                                         | 0.4                               |
| Hub genes (7)       | top_n                                                                                                  | 20                                |
| Enrichment (8)      | fdr_threshold, sources                                                                                 | 0.05, [GO:BP, GO:MF, GO:CC, KEGG] |

Submit → `POST /analyses` → redirect to `/analysis/:id`.

### Pipeline View (`/analysis/:id`)

**Layout:** Sidebar (left, fixed width 220px) + Stage panel (flex-grow, main area).

**Sidebar:**

- Analysis name at top (truncated)
- Mode badge (Guided / Auto)
- 8 stage items:
    - Completed: checkmark, muted text, clickable to view past results
    - Current running: spinner, bold text, highlighted left border
    - Awaiting approval (guided): pulsing dot, bold — user action required
    - Future: dimmed, not clickable
- "New Analysis" link at bottom → navigates to `/analysis` and clears `hf_last_analysis_id` from localStorage
- Collapsible on breakpoints < 768px (hamburger toggle)

**Stage panel:**

- Stage header: stage number + name, status badge, elapsed time
- Stage-specific content (see Stage Panels section)
- For guided mode stages awaiting approval: Approve / Reject buttons at bottom
- Export button (stage-level): JSON always available; CSV for stage 7 only
- Error state: red banner with `error_message`, "Start New Analysis" CTA
- Empty results state: informative message per stage (e.g., "No compounds found — check plant selection"), "Start New Analysis" CTA

**Polling:** `useAnalysisStatus(id)` polls every 2s while status is not `complete`/`failed`. On status change, invalidate `useAnalysis(id)` to refresh stage results.

---

## Stage Panel Designs

### Stage 1 — Compound Selection

- 3 stat cards: Total compounds, Plants covered, Average compounds/plant
- Expandable compound list (sortable table: name, MW, SMILES preview)

### Stage 2 — ADME Screening

- Stats bar: passed (green), failed (red), NP exceptions (amber) with counts + percentages
- Filterable compound table: name, MW, LogP, TPSA, HBD, HBA, NP-likeness, pass/fail badge
- Parameter summary (which thresholds were applied)

### Stage 3 — Target Identification

- Stats: target count, coverage % (compounds with at least one target)
- Gene tag list (scrollable, first 20 visible, "show all" toggle)
- Sortable target table: gene symbol, compound count, compounds list

### Stage 4 — Disease Targets

- Stats: disease target count, source breakdown (DB cache vs API)
- Table: gene symbol, UniProt accession, association score, disease name, source badge

### Stage 5 — Target Overlap

- SVG Venn diagram: three circles (compound-only, overlap, disease-only) with counts
- Stats row: overlap count, Jaccard index, p-value, significance badge (p < 0.05)
- Overlap gene list

### Stage 6 — PPI Network

- Full-panel Cytoscape.js visualization
- Node color: hub genes = sage, non-hub overlap genes = ink, network-only genes = neutral
- Edge thickness: scaled to `combined_score`
- Controls: layout toggle (fcose / grid / circle), fit-to-screen, export PNG
- Hover tooltip: gene symbol, degree centrality
- Click: highlight neighborhood (connected nodes + edges)
- Node count / edge count stats above canvas

### Stage 7 — Hub Gene Analysis

- Ranking table: rank, gene symbol, degree, betweenness, closeness, eigenvector, hub badge, hub+bottleneck badge
- Highlighted rows for hub genes (sage-faint background per design system)
- Threshold footnote (degree > mean + stdev)
- Export CSV button (this is the one stage with real CSV support)

### Stage 8 — Pathway Enrichment

- 4 tabs: GO:BP, GO:MF, GO:CC, KEGG
- Per tab: Recharts horizontal bar chart
    - Y-axis: term name (truncated to 40 chars)
    - X-axis: −log₁₀(FDR)
    - Bar fill: sage gradient
    - Tooltip: full term name, p-value, FDR, intersection size, gene list
    - Top 20 terms shown
- Total significant count badge in header

---

## TanStack Query Structure

```typescript
// Queries
usePlants()                          // GET /plants — setup form
useDiseases()                        // GET /diseases — setup form
useAnalysis(id: string)              // GET /analyses/:id — full results
useAnalysisStatus(id: string)        // GET /analyses/:id/status — polling

// Mutations
useStartAnalysis()                   // POST /analyses
useApproveStage(id: string)          // POST /analyses/:id/approve
useRejectStage(id: string)           // POST /analyses/:id/reject
useDeleteAnalysis(id: string)        // DELETE /analyses/:id

// Utilities
useExportStage(id, stage, format)    // GET /analyses/:id/export/:stage — triggers download
```

Polling config: `refetchInterval: 2000` while status is running; `refetchIntervalInBackground: false`. Stop polling when status is `complete`, `failed`, or matches `/rejected$/` (e.g., `stage_3_rejected`).

---

## Component Hierarchy

```
App
├── Layout (nav bar)
│   ├── LandingPage
│   ├── AboutPage
│   ├── SetupPage
│   │   ├── PlantSelector (combobox multi-select)
│   │   ├── DiseaseSelector (combobox single-select)
│   │   ├── ModeToggle
│   │   └── AdvancedParameters (accordion)
│   └── PipelinePage
│       ├── PipelineSidebar
│       │   └── StageNavItem × 8
│       └── StagePanelRouter → (stage 1–8 panels)
│           ├── Stage1Panel
│           ├── Stage2Panel
│           ├── Stage3Panel
│           ├── Stage4Panel
│           ├── Stage5Panel (SVG Venn)
│           ├── Stage6Panel (Cytoscape)
│           ├── Stage7Panel
│           └── Stage8Panel (Recharts)
```

Shared components: `StatCard`, `DataTable`, `StatusBadge`, `ExportButton`, `StageHeader`, `ApprovalBar`, `EmptyState`, `ErrorState`.

---

## Backend Gaps to Address

Fix before or during frontend build (update tests + `backend/CLAUDE.md` + `docs/`):

| Gap                                                                                                             | Fix                                                                                                                   |
| --------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| CSV export only works for stage 7                                                                               | Add proper CSV serialization for stages 1–5, 8                                                                        |
| Rejection is terminal (no retry)                                                                                | Frontend: on rejection, show "Start New Analysis" CTA with parameters pre-filled via URL query params or localStorage |
| `TargetRanking` unpopulated score fields (`disease_association_score`, `compound_support_score`, `final_score`) | Do not surface in UI                                                                                                  |

---

## Testing Strategy

Maps to thesis pengujian chapter (unit → integration → system).

### Unit Tests (`tests/unit/`)

- Tool: Vitest + React Testing Library
- Coverage: individual components, custom hooks, utility functions
- Key cases: StatCard renders correct values, DataTable sorts/filters, polling hook stops on complete status, parameter validation

### Integration Tests (`tests/integration/`)

- Tool: Vitest + RTL + MSW v2
- Coverage: multi-component flows with mocked API
- Key cases: guided mode approve/reject flow, auto mode polling progression, empty stage result states, API error states, setup form validation

### API Integration Tests (`tests/api/`)

- Tool: Vitest, runs against live local backend
- Coverage: full pipeline execution with real data
- Key cases: POST analyses → poll to completion, stage results parse correctly, export download triggers correctly
- Requires: `docker compose up` or local backend running

### E2E Tests (`e2e/`)

- Tool: Playwright
- Coverage: full user journeys
- Key cases:
    1. Landing → Setup → Guided pipeline → all 8 stages → export
    2. Auto mode → completion
    3. Empty results at stage 5 (no overlap)
    4. Pipeline failure (API down simulation)
    5. Browser cache restore (reload mid-pipeline)

---

## File Structure

```
frontend/
  index.html
  vite.config.ts
  tailwind.config.ts          ← hf design tokens mapped here
  src/
    index.css                 ← shadcn/ui var → hf token mapping
    main.tsx
    App.tsx                   ← routes
    lib/
      api.ts                  ← typed fetch wrappers for all endpoints
      queryClient.ts
    hooks/                    ← all TanStack Query hooks
    components/
      ui/                     ← shadcn/ui primitives (auto-generated)
      shared/                 ← StatCard, DataTable, StatusBadge, etc.
      stages/                 ← Stage1Panel … Stage8Panel
      setup/                  ← PlantSelector, DiseaseSelector, AdvancedParameters
      pipeline/               ← PipelineSidebar, StageNavItem, ApprovalBar
    pages/
      LandingPage.tsx
      SetupPage.tsx
      PipelinePage.tsx
      AboutPage.tsx
  tests/
    unit/
    integration/
  e2e/
  CLAUDE.md                   ← frontend conventions (maintain as we build)
```

---

## Documentation to Maintain

- `frontend/CLAUDE.md` — update with architectural decisions as made
- `docs/frontend.md` — frontend decisions and tradeoffs, human-readable, thesis context
- `backend/CLAUDE.md` + `docs/` — update if backend gaps are fixed
