## Task 0A — Fix playwright.config.ts npm→pnpm

- **Found:** webServer.command was "npm run dev"
- **Fixed:** Changed to "pnpm dev"
- **Files changed:** frontend/playwright.config.ts
- **Adjacent issues:** None

## Task 0C — Fix Stage8Panel.tsx FDR clamp

- **Found:** `t.fdr > 0 ? -Math.log10(t.fdr) : 300` — maps exact-zero FDR to bar value 300 (overflows chart); also allows values below 1 for non-significant terms (FDR > 0.1)
- **Fixed:** `t.fdr > 0 ? Math.max(1, -Math.log10(t.fdr)) : 1`
- **Files changed:** frontend/src/components/stages/Stage8Panel.tsx
- **Proactive audit (other stages):**
  - Stage1Panel: `result.total_compounds / result.plants_covered` — guarded (`plants_covered > 0`). Clean.
  - Stage2Panel: `(result?.passed ?? 0) / total` — guarded (`total > 0`). Clean.
  - Stage3Panel: `result.coverage_percent.toFixed(1)` — no null guard on `coverage_percent`; if backend returns null this throws. Risk.
  - Stage4Panel: `association_score` render checks `value != null`. Clean.
  - Stage5Panel: `result.jaccard_index.toFixed(3)` — guarded (`!= null && !Number.isNaN`). Clean.
  - Stage6Panel: No numeric formatting concerns found.
  - Stage7Panel: `result.threshold_betweenness?.toFixed(4)` — optional-chained. Clean.
- **Adjacent issues:** Stage3Panel `coverage_percent` has no null guard (not in scope for this task).

## Task 0B — Fix Stage6Panel.tsx CSS variables + null guard

- **Found:** `var(--primary-foreground)` used in two Cytoscape stylesheet selectors: `node[type="hub"]` (line 40) and `node[type="overlap"]` (line 44). `{tooltip.degree}` rendered without null guard (line 177).
- **Fixed:** Replaced both `var(--primary-foreground)` occurrences with `var(--hf-fg-1)`. Changed `{tooltip.degree}` to `{tooltip.degree ?? 'N/A'}`.
- **Files changed:** `frontend/src/components/stages/Stage6Panel.tsx`
- **Adjacent issues:** `node[type="overlap"]` uses `var(--hf-fg-1)` as both background-color and label color — label will be invisible against the same-color background. Flagged only; not changed per minimal-scope constraint.

## Task 0F — Add database.md update rule to CLAUDE.md

- **Fixed:** Added migration→doc sync rule to Key Conventions
- **Files changed:** CLAUDE.md
- **Adjacent issues:** None

## Task 0D — Supabase folder consolidation

- **Found:**
  - `/supabase/migrations/` (4 files): `20260516000001_create_schema.sql`, `20260516000002_create_indexes.sql`, `20260517000001_add_lipinski_source.sql`, `20260517000002_drop_unused_tables.sql`
  - `/backend/supabase/migrations/` (3 files + `.gitkeep`): `20260518000001_extend_analysis_runs.sql`, `20260518000002_verify_compound_columns.sql`, `20260518000003_add_pchembl_to_compound_targets.sql`
- **Fixed:** Moved 3 files (`20260518*.sql`) into `/supabase/migrations/`; deleted `/backend/supabase/` directory (including `.gitkeep`)
- **Final state:** `/supabase/migrations/` — 7 files in timestamp order:
  1. `20260516000001_create_schema.sql`
  2. `20260516000002_create_indexes.sql`
  3. `20260517000001_add_lipinski_source.sql`
  4. `20260517000002_drop_unused_tables.sql`
  5. `20260518000001_extend_analysis_runs.sql`
  6. `20260518000002_verify_compound_columns.sql`
  7. `20260518000003_add_pchembl_to_compound_targets.sql`
- **Files changed:** `CLAUDE.md` — added `/supabase/migrations/` row to Directory Map; `backend/CLAUDE.md` — no changes needed (no `/backend/supabase/` references found)
- **Adjacent issues:** None

## Task 0G — Rewrite frontend/CLAUDE.md

- **Action:** Rewrote to compact best-practice format
- **Lines:** 178 lines before → 55 lines after
- **Files changed:** frontend/CLAUDE.md
- **Adjacent issues:** None

## Task 0E — database.md schema sync

- **Tables audited:** source_systems, import_batches, plants, plant_aliases, compounds, compound_aliases, plant_compounds, targets, target_aliases, compound_targets, diseases, disease_aliases, disease_targets, ppi_edges, analysis_runs, analysis_run_plants, analysis_run_compounds, analysis_run_targets, analysis_run_diseases, analysis_run_ppi_edges, target_rankings, pathways, target_pathways
- **Columns added to doc:**
  - `import_batches.status text`
  - `import_batches.finished_at timestamptz`
  - `import_batches.params jsonb`
  - `import_batches.log_path text`
- **Notes enriched (already-present columns with thin descriptions):**
  - `compounds.num_ro5_violations` — added "0 = fully drug-like" clarification
  - `compounds.qed_score` — added RDKit source and 0–1 scale note
  - `compounds.np_likeness_score` — added ≥ 0.5 NP-exception threshold
  - `compounds.lipinski_source` — added enum values (`chembl_api`, `rdkit_computed`, null)
  - `compound_targets.pchembl_value` — added ≥ 5.0 active-binder threshold and STITCH-null note
  - `analysis_runs.stage_results` — added NOT NULL and DEFAULT '{}' constraint
  - `analysis_runs.mode` — added NOT NULL and DEFAULT 'auto' constraint
  - `analysis_runs.updated_at` — added NOT NULL and DEFAULT now() constraint
- **Other omissions found:** None — dropped tables (validation_reports, stg_plants, stg_plant_compounds, api_cache, source_snapshots) and dropped column (ppi_edges.source_snapshot_id) are correctly absent from the doc
- **Files changed:** .claude/docs/database.md
- **Adjacent issues:** None
