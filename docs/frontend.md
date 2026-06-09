# Herbaflow Frontend — Architecture and Design Decisions

## Overview

Herbaflow's frontend is a single-page application built with React 18 and TypeScript, served via Vite 6. It provides the primary user interface for the network pharmacology pipeline—a computational drug discovery tool that maps Indonesian medicinal plant compounds to disease targets through an 8-stage analysis workflow. The interface guides researchers through compound selection, pharmacokinetic screening, target identification, disease association, and network-based hub gene analysis, culminating in pathway enrichment predictions.

## Technology Choices and Rationale

### React 18 + TypeScript

Type safety is critical in this domain. The pipeline produces eight distinct result structures (Stage1Result through Stage8Result), each containing arrays of compounds, proteins, disease associations, and enrichment terms. TypeScript ensures type safety across these complex nested data structures and prevents runtime errors when destructuring stage results.

React 18's concurrent rendering capabilities enable smooth user experience during status polling—the UI can continue rendering while background requests fetch pipeline status every 2 seconds without blocking interaction.

### Vite 6

Vite provides sub-100ms HMR (hot module replacement) during development, critical for rapid iteration on stage panel components. The build process uses Rollup under the hood to produce optimized production bundles with automatic code splitting and tree-shaking of unused Tailwind tokens.

### TanStack Query v5

Server state management is delegated entirely to TanStack Query's `useQuery` and `useMutation` hooks. The library's built-in `refetchInterval` option handles polling without manual interval timers or cleanup bugs. When an analysis completes (terminal status reached), the query automatically stops refetching—preventing unnecessary network traffic and ensuring the UI reflects final state.

The library's automatic cache invalidation on mutations (e.g., approving a stage) eliminates the manual cache-busting logic that would otherwise scatter throughout components. Error states, loading states, and race condition prevention are built-in.

### Tailwind CSS v3 + Custom Design System

The design system lives in `design-system/colors_and_type.css` and is integrated into `tailwind.config.ts` as custom `hf-*` theme tokens. This centralization ensures visual consistency across all 8 stage panels and makes future redesigns tractable—changing a single token recolors the entire application.

The token hierarchy uses semantic naming: `hf-bg` (background), `hf-fg1` (primary text), `hf-fg2` (secondary text), `hf-border` (borders), `hf-primary` (interactive elements), `hf-sage` (data visualization), `hf-terracotta` (secondary data visualization).

### shadcn/ui

shadcn/ui provides accessible Radix primitives with sensible Tailwind defaults, eliminating the need for a heavier component library. Used throughout for Tabs (Stage 8 enrichment navigation), Command/Popover (plant species selector with search), and Accordion (advanced pipeline parameters).

### Cytoscape.js + fcose Layout

Cytoscape is the de facto standard for biological network visualization—researchers in drug discovery already expect its interaction model (pan, zoom, node selection). The `fcose` (fast compound spring embedder) layout algorithm produces cleaner hub-and-spoke topology than force-directed alternatives, particularly important for protein-protein interaction (PPI) networks where hub genes must be visually distinguished from peripheral nodes.

Cytoscape's event system is leveraged for node selection callbacks and visual feedback on hover.

### Recharts

Recharts is a lightweight, composable chart library built on D3 principles. Used in Stage 8 for the horizontal bar chart visualizing pathway enrichment (-log10 FDR values). Its composable API allows custom tooltips, legends, and responsive containers without boilerplate.

## Pipeline Architecture

The Herbaflow pipeline comprises 8 sequential stages, each producing a distinct result type:

1. **Stage 1: Compound Selection** — User selects Indonesian medicinal plant(s); backend retrieves known compounds via KNApSAcK
2. **Stage 2: ADME Screening** — Pharmacokinetic filter: absorption, distribution, metabolism, excretion properties
3. **Stage 3: Target Identification** — Compound-target binding predictions (docking or ML-based)
4. **Stage 4: Disease Target Mapping** — Maps predicted targets to disease associations (Open Targets database or ETL-cached DisGeNET)
5. **Stage 5: Target Overlap Analysis** — Venn diagram of targets shared across input diseases; identifies candidate therapeutic targets
6. **Stage 6: PPI Network Construction** — Builds protein-protein interaction network around candidate targets (STRING database)
7. **Stage 7: Hub Gene Analysis** — Computes network centrality metrics (degree, betweenness, closeness, eigenvector); hub+bottleneck criterion ranks targets by biological importance
8. **Stage 8: Pathway Enrichment** — Statistical enrichment of KEGG/Reactome pathways (hypergeometric test with FDR correction)

The UI implements two execution modes:

- **Guided Mode**: Pauses after each stage, displaying results and awaiting researcher approval (`POST /analyses/{id}/approve`) before proceeding
- **Auto Mode**: Executes all 8 stages unattended; useful for batch processing or hypothesis validation

Status polling (2-second intervals via TanStack Query) drives stage panel visibility and sidebar state. When status transitions to a terminal state (complete, failed), polling ceases automatically.

## Key Design Decisions

### Stage 5: Hand-Rolled SVG Venn Diagram

Rather than depend on a third-party Venn diagram library, Stage 5 uses hand-authored SVG with configurable circle positions and radii. This decision trades implementation simplicity (three circles, three text labels) for fine-grained visual control. The SVG is parameterized by disease count and intersection sizes, allowing researchers to intuitively grasp which targets are shared across diseases.

### Stage 8: FDR Floor Clamping

Biological data frequently produces enrichment p-values so small they underflow to zero; -log10(0) yields Infinity, which breaks Recharts' axis domain calculation. All -log10(FDR) values are clamped to a minimum of 1.0. This preserves visual ranking (smaller FDR ≈ taller bar) while keeping axis rendering stable.

### Stage 7: Centrality Metric Null Guards

The backend casts stage results via `as Stage7Result`, which silently passes through null centrality fields (e.g., if a network is too sparse to compute eigenvector centrality). Components must guard against this:

```tsx
const result = analysis?.stage_results['7'] as Stage7Result | null | undefined
if (!result?.centrality_metrics) {
  return <EmptyState message="Centrality metrics unavailable for this network" />
}
```

### Cytoscape Listener Deduplication

The `react-cytoscapejs` binding fires its `cy` callback on every render cycle. Without cleanup, event listeners accumulate, causing selection callbacks to fire multiple times. Each effect containing Cytoscape listeners begins with `cy.removeAllListeners()` to ensure a clean slate.

### Status Polling Termination

TanStack Query's `refetchInterval` combined with the `enabled` option provides graceful polling termination:

```tsx
const { data: status } = useAnalysisStatus(analysisId, {
  refetchInterval: 2000,
  enabled: !isTerminalStatus(analysis?.status)
})
```

Once `isTerminalStatus()` returns true (status is 'complete' or 'failed'), the query stops refetching. This prevents background network churn and allows the UI to remain on the final stage panel indefinitely.

## Testing Approach

### Unit Tests (Vitest + React Testing Library)

Component tests verify rendering logic and prop handling. Hooks are tested in isolation via `renderHook` from React Testing Library. Tests mock Tailwind token resolution and use MSW v2 to intercept API calls.

### Integration Tests

Full pipeline workflows are tested: guided mode approval flow, auto mode execution, error recovery, and polling state transitions. MSW mocks backend responses deterministically, allowing reproducible test scenarios.

### End-to-End Tests (Playwright)

E2E tests run against a live backend and frontend (both servers must be running). Tests exercise the complete user journey: selecting plants, choosing diseases, approving/rejecting stages, and exporting results.

## Performance Considerations

- **Code Splitting**: Vite splits stage panel components automatically; only the current stage's component is loaded
- **Image Optimization**: SVG elements (Venn diagram, stage icons) are loaded as inline assets or optimized via Vite's static asset handling
- **Query Deduplication**: TanStack Query deduplicates in-flight requests; rapidly toggling between stages does not spawn duplicate analysis status queries
- **Memoization**: Stage panels are wrapped in `React.memo` to prevent re-renders when sibling stage data changes

## Directory Structure

```
frontend/
├── src/
│   ├── components/
│   │   ├── layout/
│   │   │   ├── NavBar.tsx
│   │   │   └── Layout.tsx
│   │   ├── setup/
│   │   │   ├── PlantSelector.tsx
│   │   │   ├── DiseaseSelector.tsx
│   │   │   ├── ModeToggle.tsx
│   │   │   └── AdvancedParameters.tsx
│   │   ├── pipeline/
│   │   │   ├── PipelineSidebar.tsx
│   │   │   └── StageNavItem.tsx
│   │   ├── stages/
│   │   │   ├── Stage1Panel.tsx – Stage8Panel.tsx
│   │   ├── shared/
│   │   │   ├── StatCard.tsx
│   │   │   ├── DataTable.tsx
│   │   │   ├── StatusBadge.tsx
│   │   │   ├── ExportButton.tsx
│   │   │   ├── StageHeader.tsx
│   │   │   ├── ApprovalBar.tsx
│   │   │   ├── EmptyState.tsx
│   │   │   ├── ErrorState.tsx
│   │   │   └── ui/ (shadcn components)
│   ├── hooks/
│   │   ├── useAnalysis.ts
│   │   ├── useAnalysisStatus.ts
│   │   ├── useApproveStage.ts
│   │   ├── useRejectStage.ts
│   │   ├── useExportStage.ts
│   │   ├── usePlants.ts
│   │   ├── useDiseases.ts
│   │   └── useStartAnalysis.ts
│   ├── types/
│   │   ├── api.ts (all TypeScript interfaces matching backend schemas)
│   │   └── index.ts
│   ├── lib/
│   │   └── api.ts (typed fetch wrappers)
│   ├── mocks/
│   │   ├── handlers.ts (MSW request handlers)
│   │   └── data.ts (fixture data for all stages)
│   ├── pages/
│   │   ├── SetupPage.tsx
│   │   ├── PipelinePage.tsx
│   │   └── NotFound.tsx
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/ (Playwright — requires backend at localhost:8000)
├── public/
├── tailwind.config.ts
├── vite.config.ts
├── vitest.config.ts
├── playwright.config.ts
├── tsconfig.json
└── package.json
```

## Summary

Herbaflow's frontend is architected around the 8-stage pipeline abstraction. TypeScript ensures correctness of complex result structures; TanStack Query eliminates manual polling logic; Tailwind's design system tokens enable rapid, consistent styling; and Cytoscape provides domain-familiar network visualization. The combination of these technologies allows researchers to intuitively explore drug discovery hypotheses while maintaining code quality and test coverage.
