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

## Setup Form — Input Modes

The setup form (`SetupView.tsx`) lets the researcher choose how to supply the plant-side and
disease-side inputs independently, via a radio-button fieldset for each side.

### Plant input modes (3 options)

| Mode | Control shown | What it contributes |
|---|---|---|
| `selection` (default) | Plant multiselect (catalog search) | Selected plant UUIDs → `plant_ids`; Stage 1 runs the KNApSAcK compound lookup |
| `manual_compounds` | `CompoundValidateBox` (SMILES/name resolve) | Resolved compound UUIDs seeded into Stage 1 via `stage_edits`; Stage 1 lookup is skipped (`not_applicable`) |
| `manual_targets` | `TargetValidateBox` (gene-symbol/accession resolve) | Resolved target UUIDs seeded into Stage 3 via `stage_edits`; Stages 1 and 2 are skipped (`not_applicable`) |

### Disease input modes (2 options)

| Mode | Control shown | What it contributes |
|---|---|---|
| `selection` (default) | Disease single-select (catalog combobox) | Selected disease UUID → `disease_id`; Stage 4 reads the seeded `disease_targets` table |
| `manual_disease_targets` | `TargetValidateBox` (gene-symbol/accession resolve) | Resolved target UUIDs seeded into Stage 4 via `stage_edits`; `disease_id` is NULL; Stage 4's DB read is skipped |

In both manual modes an **optional free-text label** field appears (≤ 200 chars). The label is
display-only — it is stored in `parameters.labels` but is never canonicalized and is never used as
an identity. Manual entities create **no catalog rows** (`plants` / `diseases`); they exist only
within the run.

### Run header display name

The run header shows a per-side display name:
- **Selection mode** — the catalog name(s) of the selected plants or disease.
- **Manual mode with a label** — the free-text label the researcher supplied.
- **Manual mode without a label** — "N/A".

---

## Stage rendering — `not_applicable` and `user_provided` states

### `not_applicable` stages

When a stage does not apply to the chosen input mode (e.g. Stage 1 in `manual_targets` mode),
`stage_results[n].state` is `"not_applicable"`. The stage panel renders a **greyed "Not applicable
for this run" block** in place of the normal results view; no approval bar or param panel is shown.

### `user_provided` stages

When a stage was pre-filled by the user at setup (or later edited), `stage_results[n].state` is
`"user_provided"`. The stage panel shows the normal results view but adds a **"Provided by you"
badge** next to the stage heading to signal that the content came from the researcher, not from a
pipeline computation.

---

## Guided Machinery UX

### Param panel (param-bearing stages)

Each stage that carries tunable parameters (currently Step 2 — ADME) renders a collapsible
**param panel** above its results. The panel lists every parameter with its description, its
default, and (where applicable) the recommended range in the format `(default X, recommended
lo–hi)`. Input fields validate against the contract's **hard bounds** only — the backend's
enforcement threshold — not the advisory recommended range.

The **Redo** button at the bottom of the panel is armed only when at least one value differs from
the **frozen** value stored in `parameters.adme` (i.e., the value the run was actually computed
with, not the contract default). Submitting Redo calls `POST /analyses/{id}/reset-from/{stage}`
with the changed values; the backend validates, merges, clears downstream stages, and re-runs.

### In-stage add/remove (Step 1 — compound selection)

Step 1 renders an `EditableEntityList` over its compound result. Each computed row has a remove
control; a separate add box (reusing the `CompoundValidateBox` from setup) resolves a SMILES or
name through `POST /compounds/validate` before adding. Rows are tagged visually:

| Tag | Meaning |
|---|---|
| `computed` | Came from the plant-compound lookup |
| `user-added` | Added by the researcher after the stage ran |
| `user-removed` | Removed by the researcher; still shown (greyed) but excluded from the forward set |

The add box is disabled once the compound cap (2,000) is reached; the disabled state shows
`"cap / current"` so the researcher knows how many slots remain. Submitting calls
`POST /analyses/{id}/stages/{stage}/edit`; the backend reapplies the durable edit layer and
re-runs from Step 2.

### Approval bar

An **ApprovalBar** (`"Approve & Continue"` button) is visible **only on the current awaiting
stage** — i.e., when the run status is `stage_{N}_awaiting_approval` and `N` matches the
displayed stage. Approving calls `POST /analyses/{id}/advance`. The bar is hidden once the stage
is past or the run is in auto mode.

### Step 2 results view

The ADME results panel renders two tables — **Passed** and **Filtered** — switchable by tab.
Each row carries:

- The descriptor values (MW, logP, HBD, HBA, TPSA, rotatable bonds).
- `qed_score` (QED — Quantitative Estimate of Drug-likeness, 0–1).
- `descriptor_source` badge: `etl` (DB columns), `rdkit` (computed at screen time), or
  `unscreened`.
- Status badges: `PAINS`, `NP-bypass`, `unscreened`, `could-not-screen` where applicable.
- A `reason` column on filtered rows (e.g. `"2 Lipinski violation(s)"`, `"fails Veber: TPSA"`).

A **CSV download** button exports the full passed + filtered compound list with all descriptor
columns. A tools-and-data-sources footer lists the screening rules applied (Lipinski / Veber /
NP-bypass / PAINS) and the parameter values used for the run.

### Step 3 — Target Identification

**Components:** `src/components/stages/Stage3View.tsx`, `src/components/stages/StpDialog.tsx`,
`src/components/TargetValidateBox.tsx`.

**Results view:** Renders a target table keyed by **UniProt accession + gene symbol** (never
a DB UUID). Each computed row carries an explicit `prediction_method` column (`chembl_bioactivity`
or `pubchem_bioassay` — the only methods written as edges) and a `pchembl_value` for ChEMBL rows.
Manually added targets (including STP paste-back) are run-scoped and carry no edge/method. A **per-compound
coverage** summary is always visible; compounds with zero targets are surfaced explicitly.

**CSV export:** Columns are UniProt accession + gene symbol — the stable external identifiers —
not internal DB UUIDs.

**STP dialog (`StpDialog.tsx`):** A modal for pasting SwissTargetPrediction results.
- Compound selector orders by ascending target-count (least-covered first).
- Selected compound's SMILES is shown with a copy button (populated from `stage_results["2"].passed`
  rows, which now expose `smiles` + `inchi_key`).
- Paste area is parsed by `src/lib/stp.ts` (the canonical home for the STP CSV parser; keys on the
  SwissTargetPrediction `Probability*` header, also accepting plain `Probability`, with
  `Uniprot ID` / `Common name`).
- Preview table shows parsed rows; the resolved accessions are added to the run's Stage-3 set via the
  manual target-add path (`POST /targets/validate` → `POST /analyses/{id}/stages/3/edit`). There is no
  STP import endpoint.

**Edit controls:** The `EditableEntityList` / `ParamPanel` machinery is now param-group-generic;
Step 3 uses the `target` param group (parameters `min_pchembl` + `min_assay_confidence`). Manual
target addition via `TargetValidateBox` → `POST /targets/validate` writes a run-scoped inclusion
in the stage set (no `compound_targets` edge); STP paste-back via `StpDialog` resolves the pasted
accessions the same way and adds them to the run's Stage-3 set through the manual target-add path
(`POST /analyses/{id}/stages/3/edit`) — also run-scoped, no `compound_targets` edge. See
Limitations in `docs/testing.md`.

### Step 4 — Disease Target Collection

**Component:** `src/components/stages/Stage4View.tsx`.

**Results view:** Renders the disease→target set collected from the ETL-seeded `disease_targets`
read. Summary **cards** lead (e.g. target count, the `min_score` in effect); a **score table**
lists each target keyed by UniProt accession + gene symbol with its Open Targets association
score, ordered by score descending. Manual disease-targets have no score (shown as `—`). The
table offers **add / remove** controls via the shared manual target-add path (`TargetValidateBox`
→ `POST /targets/validate` → `POST /analyses/{id}/stages/4/edit`). An empty disease-target side is
surfaced as an honesty note (count 0), not an error.

**CSV export:** Columns are UniProt accession + gene symbol + Open Targets score — stable external
identifiers, never internal DB UUIDs.

**Param panel + Redo:** A collapsible param panel exposes `min_score` (the
`DISEASE_TARGETS_PARAMS` group; default 0.3, hard range 0–1, advisory band 0.1–0.5). Redo submits
`POST /analyses/{id}/reset-from/4` and re-runs from Step 4.

**Footer:** A tools-and-data-sources footer attributes the data to Open Targets (consumed as an
ETL-time source) and lists the `min_score` used for the run.

**Rendering:** Like the other stages, the view renders by `stage_state` (`computed` vs
`user_provided`) — a non-empty edit layer marks the set user-provided.

---

### Step 5 — Target Overlap

**Component:** `src/components/stages/Stage5View.tsx`.

**Results view:** Read-only — Stage 5 has **no parameters** and is not an entity stage. Summary
**cards** lead: overlap count, the Jaccard index, the hypergeometric p-value, and a clear
**significant / not-significant badge** (driven by `hypergeometric.significant` and the
`non_significant_overlap` flag). An **overlap table** lists each shared target by gene symbol +
UniProt accession (linked to the UniProt entry) with its Open Targets score, paginated like
the other stages. Stage 5 intersects the **run-scoped** Stage-3 (compound→target) and Stage-4
(disease→target) sets from `stage_results` — including user-added targets — on the canonical
`target_id`, **not** the global edge tables. A 0-overlap run is a terminal hard-stop.

**CSV export:** gene symbol + UniProt accession + Open Targets score + UniProt source URL.

**No param panel.** The data-sources footer states the fixed method (Jaccard + one-sided
hypergeometric, N = 20,000, α = 0.05) — method constants, not configuration.

---

### Step 6 — PPI Network

**Component:** `src/components/stages/Stage6View.tsx`.

**Results view (computed):** Summary **cards** lead (node count, edge count, `min_confidence`,
`network_type`, unmapped count); an **edge-list table** lists each STRING interaction (source,
target, confidence 0–1), paginated, with **CSV export**. A "capped" note appears when the top-N cap
was applied.

**Overlap-too-large (blocked):** when `stage_results["6"].blocked` is true, the edge table is
replaced by a prompt explaining the overlap (`overlap_count`) exceeds the STRING ceiling
(`max_proteins`), with an **"Enable top-N & Redo"** action (Redo with `allow_top_n_cap: true`) and a
hint to narrow the inputs upstream. A guided run parks here; an auto run hard-fails (AD-6).

**Param panel + Redo:** the `ppi` group is exposed via the generic `ParamPanel` — `max_proteins`
(numeric), `allow_top_n_cap` (checkbox), and `min_confidence` / `network_type` as **enum selects**
(`ParamPanel` was extended with generic `selectKeys` support for this). Redo submits
`POST /analyses/{id}/reset-from/6`.

**Footer:** attributes the network to STRING (human only, species 9606). Graph *visualisation* is
deferred to the Phase-5 design pass — the edge list is the current surface.

---

### Step 7 — Hub Genes

**Component:** `src/components/stages/Stage7View.tsx`.

**Results view (computed):** Summary **cards** lead (node count, ranked count, ranking metric,
`composite_weight`); a **hub table** lists each hub-ranked protein with columns for rank, gene
symbol (linked to UniProt via `source_url`), and all four centrality values (degree, betweenness,
closeness, eigenvector) plus the composite score, ordered by rank ascending. The `"network_too_small"`
flag renders as a dismissible notice (tiny/sparse network — informational, not an error). The
`"eigenvector_fallback"` flag is surfaced as a footnote on the eigenvector column header.

**CSV export:** columns are rank + gene symbol + UniProt accession + degree + betweenness +
closeness + eigenvector + composite score.

**Param panel + Redo:** the `hub_genes` group is exposed via `ParamPanel` — `top_n` (numeric),
`use_hub_bottleneck` (checkbox), and `composite_weight` (numeric; disabled and greyed when
`use_hub_bottleneck` is false). Redo submits `POST /analyses/{id}/reset-from/7`.

**Footer:** attributes the centrality computation to networkx (Python, undirected graph) and cites
the Yu 2007 hub-bottleneck composite.

---

### Step 8 — Pathway Enrichment (terminal)

**Component:** `src/components/stages/Stage8View.tsx`.

**Results view (computed):** Summary **cards** lead (enriched-term count, input gene count,
background gene count, FDR threshold, correction method); an **enrichment table** lists each
significant term with columns for source (GO:BP / GO:MF / GO:CC / KEGG), term ID, term name,
FDR-corrected p-value (rendered as `−log₁₀(p)`; clamped to a minimum of 1.0 to prevent `Infinity`
from underflowing), term size, intersection size, and the intersection gene list. Paginated and
CSV-exportable. A **0-term result** renders as an honest-null notice (no enrichment found at the
current threshold — not an error; the run is still `complete`). A **degraded result**
(`stage_results["8"].degraded = true`) renders a distinct notice (g:Profiler outage; pipeline
completed but enrichment unavailable — the run is still `complete`).

**CSV export:** columns are source + term ID + term name + p-value + term size + intersection
size + intersection genes (pipe-delimited).

**Param panel + Redo:** the `enrichment` group is exposed via `ParamPanel` — `significance_threshold`
(numeric), `min_term_size` (numeric), `correction` as an **enum select** (`g_SCS` / `fdr` /
`bonferroni`), and `no_iea` (boolean). The `sources` multi-select is deferred to Phase 5. Redo
submits `POST /analyses/{id}/reset-from/8`.

**Pipeline-complete affordance:** when `analysis.status === "complete"` and Stage 8 is the
active stage, the view surfaces a **"Pipeline complete"** banner (distinct from the per-stage
approval bar) with the run's `completed_at` timestamp. The downloadable results bundle is offered
by the run-level **Download results** action (see below).

**Footer:** attributes enrichment to g:Profiler (Raudvere 2019), lists the sources queried and
the custom background (Stage-3 compound-target universe).

---

## Results download (completed runs)

`RunView` shows a single **Download results** action (`DownloadResults`) once the run is
`complete`. It is a plain anchor with `download` pointing at `GET /analyses/{id}/export` — a
**binary** zip, so it deliberately bypasses the typed query SDK and is fetched directly by the
browser (the backend sets `Content-Disposition`). The export URL is built by
`src/lib/exportUrl.ts` (`exportBundleUrl`) from the single `API_BASE_URL` exported by
`src/lib/api.ts` — the same base the generated client uses (overridable via `VITE_API_BASE_URL`).

The zip contains four files: `ctp-nodes.csv` + `ctp-edges.csv` (the compound–target–pathway
network for Cytoscape), `docking.csv` (hub × binding-compound pairs, AlphaFold id = the hub's
UniProt accession), and `report.md` (run identity, inputs, frozen params, per-stage counts,
labels-only provenance). The backend also exposes each artifact at its own endpoint
(`…/export/ctp-nodes.csv`, `…/export/ctp-edges.csv`, `…/export/docking.csv`, `…/export/report`).
This run-level bundle is **distinct** from the per-stage CSV downloads each `StageNView` already
offers (those export a single stage's table; this exports the assembled cross-stage handoff).

---

## Summary

Herbaflow's frontend is architected around the 8-stage pipeline abstraction. TypeScript ensures
correctness of complex result structures; TanStack Query eliminates manual polling logic; Tailwind's
design system tokens enable rapid, consistent styling; and Cytoscape provides domain-familiar
network visualization. The combination of these technologies allows researchers to intuitively
explore drug discovery hypotheses while maintaining code quality and test coverage.
