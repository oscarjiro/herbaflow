# Herbaflow Data & ETL Audit Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Audit ETL pipelines and live database for data quality, scientific accuracy, and academic soundness in a network pharmacology context — identify and fix all gaps.

**Architecture:** 6 sequential phases with intra-phase parallelism. Parallel subagents (e.g. Phase 0) append collectively to their `phase-N.md` after all complete; sequential tasks in all other phases append after each individual task. Breaking changes list affected backend + frontend files before applying. Auto-commits enabled throughout.

**ETL re-run policy:** Selective re-runs only — in order of preference: (a) `load.py --upsert` reload from existing ETL outputs if data shape is correct, (b) re-run only the failing ETL module if source data quality is the issue, (c) `load.py --reset` full wipe + re-seed as last resort. Consult user per phase before any re-run.

**Tech Stack:** Python ETL (FastAPI backend), PostgreSQL via Supabase MCP, PubChem/ChEMBL/STRING DB/Open Targets/g:Profiler APIs, RDKit (in ETL venv), Vitest + Playwright.

**Effort levels:** [M] medium · [H] high · [xH] extra-high (scientific/academic scrutiny)

**Token discipline:** Never read full CSVs. For ETL outputs: read headers + 3 sample rows + manifest JSON only. Use Supabase MCP for all live DB queries.

**Adjacent bugs:** Proactively log any bugs or problems found outside a task's direct scope — append to the current phase's `.md` file under an "Adjacent Findings" section and continue. Do not fix out-of-scope issues mid-task; document them for a follow-up pass.

---

## Context

Previous QA sessions (Phase 2–5) fixed frontend rendering, sidebar failures, Stage 8 g:Profiler parameter bug, and backend model issues. This session focuses **upstream**: raw data quality, ETL correctness, schema health, and the scientific/academic defensibility of the analysis methodology.

Known issues going in:
- Duplicate plant rows in DB (Curcuma longa: one row with ~180 compounds, one with 1)
- `family_name` bulk-empty in plants table
- Ambiguity about ID format (`pl_` prefix vs plain UUID)
- All-caps compound names (CHOLESTEROL, MYRCENE) — canonical or bug?
- ADME coverage gaps — many compounds may lack full Lipinski descriptor set
- ADME screening approach (Lipinski + Veber + NP exception) needs scientific justification
- STRING DB confidence threshold not documented/justified
- Stage 7 has duplicate output fields (`hub_genes` == `ranked`, `threshold_degree` == `hub_degree_threshold`)
- `apply_pains: false` config is declared but never referenced in stage2
- `ImportBatch.params` field missing from SQLModel model (migration has it, ORM doesn't)
- `disease_id` not persisted or returned by `GET /analyses` (root cause found: `create_run()` ignores it)
- ID format inconsistency: ETL uses UUID v5 for plant/compound IDs; Stage 3 backend generates MD5-prefixed target IDs (`tgt_...`, `ct_...`) — strategy mismatch across entity types
- All entity ID formats unverified: `plant_id`, `compound_id`, `target_id`, `disease_target_id` may have inconsistent prefix conventions

---

## Pre-flight

- [ ] Create `docs/data-audit-session/` directory (may already exist from prior audit sessions — check first)
- [ ] Verify Supabase MCP is connected: run `list_tables` and confirm tables are visible
- [ ] Read `etl/shared/utils.py` — understand `stable_id()`, `normalize_whitespace()`, `to_key()`
- [ ] Implement `--reset` flag in `etl/load/load.py`: truncate ALL public tables via `TRUNCATE ... CASCADE` (full wipe including `analysis_runs`), then re-insert from current ETL output CSVs. Enables clean-slate re-seeding without dropping schema.
  - Commit: `feat(etl/load): add --reset flag for full wipe + re-seed`

---

## Phase 0: Live Database Baseline [H]

**Goal:** Establish ground truth of what is actually in the database. Confirm or refute every known issue before touching code.

**Dispatch 3 parallel subagents** — all read-only Supabase MCP queries.

**Append findings to `docs/data-audit-session/phase-0.md` after all 3 complete.**

---

### Task P0-A: Plant Table Audit

- [ ] Run the following queries via Supabase MCP:

```sql
-- Duplicate canonical names
SELECT canonical_scientific_name, COUNT(*) AS cnt
FROM plants
GROUP BY canonical_scientific_name
HAVING COUNT(*) > 1
ORDER BY cnt DESC
LIMIT 20;

-- family_name coverage
SELECT
  COUNT(*) AS total,
  COUNT(family_name) AS with_family,
  COUNT(*) FILTER (WHERE family_name IS NULL OR family_name = '') AS missing_family
FROM plants;

-- ID format sample (UUID vs prefixed)
SELECT plant_id, canonical_scientific_name, family_name
FROM plants
LIMIT 5;

-- Curcuma longa specifically
SELECT
  p.plant_id,
  p.canonical_scientific_name,
  p.family_name,
  p.gbif_usage_key,
  p.confidence,
  COUNT(pc.compound_id) AS compound_count
FROM plants p
LEFT JOIN plant_compounds pc ON pc.plant_id = p.plant_id
WHERE lower(p.canonical_scientific_name) LIKE '%curcuma%'
GROUP BY p.plant_id, p.canonical_scientific_name, p.family_name, p.gbif_usage_key, p.confidence;
```

- [ ] Record in phase-0.md: total plant count, duplicate count, family_name null%, Curcuma longa rows

---

### Task P0-B: Compound Table Audit

- [ ] Run via Supabase MCP:

```sql
-- ADME coverage by lipinski_source
SELECT
  lipinski_source,
  COUNT(*) AS total,
  COUNT(molecular_weight) AS has_mw,
  COUNT(logp)             AS has_logp,
  COUNT(tpsa)             AS has_tpsa,
  COUNT(hbond_donors)     AS has_hbd,
  COUNT(hbond_acceptors)  AS has_hba,
  COUNT(rotatable_bonds)  AS has_rotb,
  COUNT(qed_score)        AS has_qed,
  COUNT(np_likeness_score) AS has_np,
  COUNT(smiles)           AS has_smiles,
  COUNT(inchi_key)        AS has_inchikey
FROM compounds
GROUP BY lipinski_source
ORDER BY total DESC;

-- All-caps name sample
SELECT compound_id, canonical_name, pubchem_cid, chembl_id, lipinski_source
FROM compounds
WHERE canonical_name = upper(canonical_name)
  AND length(canonical_name) > 3
LIMIT 20;

-- Alias type distribution
SELECT alias_type, COUNT(*) AS cnt
FROM compound_aliases
GROUP BY alias_type
ORDER BY cnt DESC;

-- Compounds with zero aliases
SELECT COUNT(*) AS compounds_without_aliases
FROM compounds c
WHERE NOT EXISTS (
  SELECT 1 FROM compound_aliases ca WHERE ca.compound_id = c.compound_id
);
```

- [ ] Record: total compounds, ADME null rates per field, all-caps %, alias type distribution

---

### Task P0-C: Schema Health Check

- [ ] Run via Supabase MCP:

```sql
-- Row counts all tables
SELECT schemaname, tablename, n_live_tup AS rows
FROM pg_stat_user_tables
WHERE schemaname = 'public'
ORDER BY n_live_tup DESC;

-- Target coverage
SELECT
  COUNT(*) AS total,
  COUNT(uniprot_accession) AS has_uniprot,
  COUNT(gene_symbol) AS has_gene_symbol,
  COUNT(protein_name) AS has_protein_name
FROM targets;

-- Disease ontology coverage
SELECT ontology_source, COUNT(*) AS cnt
FROM diseases
GROUP BY ontology_source;

-- analysis_runs: disease_id present?
SELECT COUNT(*) AS total, COUNT(disease_id) AS with_disease_id
FROM analysis_runs;

-- ImportBatch: does params column exist in DB?
SELECT column_name, data_type, is_nullable
FROM information_schema.columns
WHERE table_name = 'import_batches'
ORDER BY ordinal_position;

-- Missing indexes check (pg_indexes)
SELECT indexname, tablename, indexdef
FROM pg_indexes
WHERE schemaname = 'public'
  AND tablename IN ('targets', 'compounds', 'analysis_runs')
ORDER BY tablename, indexname;
```

- [ ] Record: row counts per table, target coverage %, disease coverage, disease_id in analysis_runs, ImportBatch schema

---

## Phase 1: Plant Data Quality [H]

**Goal:** Fix duplicate plants and missing family column at the ETL source. Document impact.

**Files to read:**
- `etl/knapsack/main.py`
- `etl/knapsack/out/plants.csv` — headers + 3 rows only
- `etl/plants/02_normalize_taxonomy/run.py`
- `etl/plants/03_match_gbif/run.py`
- `etl/plants/04_build_canonical/run.py` (or part_1.py + part_2.py if split)
- `etl/plants/03_match_gbif/out/gbif_matches.csv` — headers + 3 rows

---

### Task P1-A: Trace Duplicate Plant Root Cause

- [ ] Read `etl/knapsack/main.py` — find deduplication logic; note what field is used to deduplicate (raw name? ID? link?)
- [ ] Read `etl/plants/02_normalize_taxonomy/run.py` — note if any deduplication occurs here
- [ ] Read `etl/plants/04_build_canonical/run.py` — note how UUID v5 is assigned; what is the namespace key input?
- [ ] Determine the root cause:
  - **Likely**: KNApSAcK table has multiple rows per species (variant names/accessions). Dedup is on raw string → "Curcuma longa L." and "Curcuma longa" survive as separate entries. GBIF may return the same or different `usageKey` for each → if different keys: two different UUIDs → two DB rows.
  - **Alternative**: GBIF match fails for one variant → fallback key produces a different UUID.
- [ ] Verify hypothesis by checking: does `etl/knapsack/out/plants.csv` show 2+ Curcuma longa rows? (headers + grep for "Curcuma", no full read)
- [ ] Document root cause in `docs/data-audit-session/phase-1.md`

---

### Task P1-B: Fix Knapsack Deduplication

- [ ] Read `etl/knapsack/main.py` fully
- [ ] Fix: normalize species name before deduplication
  - Strip trailing authorship tokens: ` L.`, ` Blume`, ` Roxb.`, ` Willd.`, etc.
  - Lowercase + strip whitespace
  - Keep row with the most compound associations (highest count in the scrape)
  - Example fix:
    ```python
    import re
    
    def normalize_species(name: str) -> str:
        # strip authorship suffixes: trailing uppercase initials and known names
        name = re.sub(r'\s+[A-Z][a-z]*\.?(\s+[A-Z][a-z]*\.?)*$', '', name.strip())
        return name.lower().strip()
    
    # Dedup: group by normalized name, keep row with max compound count
    df['_norm'] = df['species_name'].map(normalize_species)
    df = df.sort_values('compound_count', ascending=False).drop_duplicates(subset='_norm')
    df = df.drop(columns='_norm')
    ```
- [ ] **Impact**: knapsack output CSV changes → downstream plants pipeline must be re-run to clean duplicates → load.py must be run with `--upsert` to remove orphaned DB rows
- [ ] Document impact in phase-1.md under "Breaking Changes"
- [ ] Commit: `fix(etl/knapsack): normalize species name before deduplication`

---

### Task P1-C: Fix Missing family_name

- [ ] Read `etl/plants/03_match_gbif/run.py` — find where GBIF API response is parsed
- [ ] Check GBIF API response structure: `family` field is a top-level string in both `match` and `usage` endpoints
  - GBIF `/v1/species/match` returns: `{ "family": "Zingiberaceae", "usageKey": 12345, ... }`
  - Look for where `family` is extracted from the parsed response dict
- [ ] Read headers + 3 rows of `etl/plants/03_match_gbif/out/gbif_matches.csv` — does it have a `family` column? Is it populated?
- [ ] Read `etl/plants/04_build_canonical/run.py` — find where `family_name` is written to the output CSV
- [ ] Fix wherever `family` is being dropped or not mapped to `family_name`
  - Typical fix: ensure `row['family_name'] = gbif_response.get('family', '')` is not accidentally filtered out
- [ ] Document fix in `docs/data-audit-session/phase-1.md`
- [ ] Commit: `fix(etl/plants): propagate family_name from GBIF match response`

---

### Task P1-D: ID Format Verification (All Entity Types)

- [ ] Audit ID format across ALL entity types via Supabase MCP:
  ```sql
  SELECT plant_id FROM plants LIMIT 1;
  SELECT compound_id FROM compounds LIMIT 1;
  SELECT target_id FROM targets LIMIT 1;
  SELECT disease_target_id FROM disease_targets LIMIT 1;
  ```
- [ ] Read `backend/analysis/stages/stage3_targets.py` — confirm whether it generates MD5-prefixed IDs (`tgt_...`, `ct_...`) inconsistent with ETL UUID v5 strategy
- [ ] Read `etl/shared/utils.py` — confirm `stable_id()` output format (prefix or bare UUID v5?)
- [ ] Read `etl/load/load.py` — confirm whether prefixes are added or stripped during load
- [ ] **Decision gate**: Present findings to user — which entity types have prefixed IDs, which have bare UUIDs, where inconsistencies exist between ETL and backend. Recommend one of:
  - **Keep prefixes as-is**: `pl_`, `tgt_`, etc. are human-readable type tags (convention in CLAUDE.md). Academically defensible as stable deterministic typed identifiers. Document rationale.
  - **Migrate to bare UUIDs**: large breaking change — all FKs, `etl/load/load.py`, `backend/analysis/stages/stage3_targets.py`. Only if inconsistency is severe enough to warrant it.
  - **Fix inconsistency only**: align Stage 3 backend target IDs with ETL UUID v5 strategy without full migration.
  - **Wait for user confirmation before proceeding.**
- [ ] Commit documentation after decision: `docs(database): document ID format convention and consistency findings`

---

## Phase 2: Compound Data Quality [H]

**Goal:** Confirm all-caps names are canonical, assess ADME coverage, verify alias completeness.

**Files:**
- `etl/compounds/02_normalize/run.py`
- `etl/compounds/04_enrich/run.py` (structure/logic only, skip large data vars)
- `etl/compounds/04_enrich/patch_missing_lipinski.py`
- `etl/compounds/05_build_canonical/run.py`
- `etl/compounds/07_export/out/compounds.csv` — headers + 3 rows (one all-caps name, one mixed-case name, one with null ADME)

---

### Task P2-A: Compound Name Canonicality [H]

- [ ] Read `etl/compounds/04_enrich/run.py` — find what field from ChEMBL/PubChem is used as `canonical_name`
  - ChEMBL: `pref_name` field — this IS uppercase for most small molecules (ChEMBL convention)
  - PubChem: `IUPACName` field — typically mixed-case systematic name
  - Determine which source wins in the pipeline
- [ ] From Phase 0 all-caps sample: check 5 entries — verify their `chembl_id` is non-null and matches ChEMBL's `pref_name` convention
- [ ] Query Supabase: `SELECT canonical_name, chembl_id FROM compounds WHERE canonical_name = upper(canonical_name) AND chembl_id IS NOT NULL LIMIT 5;` — then spot-check one or two against ChEMBL directly if needed
- [ ] **Expected result**: all-caps names are correct ChEMBL `pref_name` values (CHOLESTEROL, MYRCENE, QUERCETIN etc. are all uppercase in ChEMBL). Not a bug.
- [ ] **If bug found** (e.g., names uppercased by normalization code rather than sourced that way): fix in `etl/compounds/02_normalize/run.py`
- [ ] Document verdict in `docs/data-audit-session/phase-2.md`
- [ ] Commit if fix needed; otherwise commit docs only: `docs(etl/compounds): verify all-caps canonical names are ChEMBL pref_name convention`

---

### Task P2-B: ADME Coverage Assessment [H]

Using Phase 0 ADME coverage numbers:

- [ ] Calculate null rates for critical fields:
  - `molecular_weight` — must be near 0% null (PubChem covers almost all)
  - `logp` — acceptable < 15% null (some compounds not in ChEMBL/RDKit-computable)
  - `tpsa` — acceptable < 15% null
  - `qed_score` — may be higher null (ChEMBL only, no RDKit fallback)
  - `np_likeness_score` — may be 30-50% null (ChEMBL only, no RDKit fallback)
- [ ] **Critical check**: if `np_likeness_score` null rate > 30%, the NP exception pathway in Stage 2 ADME is blind for those compounds — they can't benefit from the NP exception even if they are natural products
- [ ] **If np_likeness_score null rate > 20%**: add RDKit NP score computation to `etl/compounds/04_enrich/patch_missing_lipinski.py`

  ```python
  # Add to patch_missing_lipinski.py after RDKit Lipinski pass:
  from rdkit.Chem import RDConfig
  import os, sys
  sys.path.append(os.path.join(RDConfig.RDContribDir, 'SA_Score'))
  # NP-likeness requires the npscorer from RDKit Contrib:
  sys.path.append(os.path.join(RDConfig.RDContribDir, 'NP_Score'))
  import npscorer
  fscore = npscorer.readNPModel()
  
  def compute_np_score(smiles: str) -> float | None:
      mol = Chem.MolFromSmiles(smiles)
      if mol is None:
          return None
      return npscorer.scoreMol(mol, fscore)
  
  # Apply to rows where np_likeness_score is null but smiles is not null
  mask = df['np_likeness_score'].isna() & df['smiles'].notna()
  df.loc[mask, 'np_likeness_score'] = df.loc[mask, 'smiles'].map(compute_np_score)
  df.loc[mask, 'lipinski_source'] = df.loc[mask, 'lipinski_source'].fillna('') + '+rdkit_np'
  ```

- [ ] Document thresholds and verdict in phase-2.md
- [ ] Commit if patched: `fix(etl/compounds): compute NP-likeness via RDKit for compounds missing ChEMBL NP score`

---

### Task P2-C: Alias Completeness [M]

- [ ] From Phase 0 alias type distribution: verify expected types exist — `chembl_id`, `pubchem_cid`, `cas_id`, `inchi_key`, `synonym`
- [ ] Check: how many compounds have zero aliases (from P0-B query)
  - Zero-alias compounds are "orphaned" — no external ID linkage — problematic for reproducibility
- [ ] Query: `SELECT c.compound_id, c.canonical_name, c.chembl_id, c.pubchem_cid FROM compounds c WHERE NOT EXISTS (SELECT 1 FROM compound_aliases ca WHERE ca.compound_id = c.compound_id) LIMIT 10;`
- [ ] If orphaned compounds exist: check if their `chembl_id`/`pubchem_cid` columns are populated in the main table
  - If yes: the alias creation step in `05_build_canonical/run.py` failed to emit alias rows for them
  - If no: they have no external IDs at all — acceptable for compounds sourced from raw KNApSAcK with no PubChem match
- [ ] Document findings; if bug in alias creation: fix in `etl/compounds/05_build_canonical/run.py`
- [ ] Commit docs: `docs(etl/compounds): document alias completeness findings`

---

## Phase 3: ADME Screening Scientific Review [xH]

**Goal:** Validate that the compound screening methodology is scientifically and academically defensible for network pharmacology of Indonesian medicinal plants.

**Files:**
- `backend/analysis/stages/stage2_adme.py`
- `backend/analysis/models.py` (AdmeParams section)

---

### Task P3-A: Scientific Justification of Screening Rules [xH]

- [ ] Read `backend/analysis/stages/stage2_adme.py` fully
- [ ] Read `backend/analysis/models.py` — `AdmeParams` dataclass

**Evaluate each component:**

**Lipinski Rule of Five (RO5)**
- MW ≤ 500 Da, logP ≤ 5, HBD ≤ 5, HBA ≤ 10
- Original purpose: predict oral bioavailability of *synthetic* drug candidates (Lipinski et al., Adv. Drug Deliv. Rev., 1997/2001)
- For natural products: many bioactive NPs violate RO5 (taxol MW ~854, cyclosporine MW ~1202)
- **Verdict**: RO5 alone is overly restrictive for a natural product pipeline; but the NP exception pathway compensates. Defensible *with* the exception, not alone.
- **Action**: Document this nuance explicitly in code and docs.

**Veber Rules (TPSA ≤ 140, RotBonds ≤ 10)**
- Designed for intestinal permeability in rats (Veber et al., J. Med. Chem., 2002)
- Applied as secondary filter alongside RO5 — reduces false positives from highly flexible/polar molecules
- **Verdict**: Appropriate; standard complement to RO5. TPSA 140 threshold is the widely-used cut-off.

**NP Exception (np_likeness_score ≥ 0.5)**
- NP likeness score from Ertl & Schuffenhauer 2008 (J. Nat. Prod., 71:951-959)
- Score > 0: positive NP character; > 0.5: strong NP character
- Threshold 0.5 is defensible for classifying "natural product-like" and thus exempting from RO5
- **Verdict**: Scientifically sound. Threshold 0.5 has literature backing.

**PAINS Filter (apply_pains: false)**
- Pan-Assay Interference Compounds (Baell & Holloway, J. Med. Chem., 2010)
- PAINS identifies structures causing false positives in biochemical assays
- For computational/network pharmacology (no assay screening), PAINS is less critical
- However: flagging is good practice for publication-grade work
- **Verdict**: Acceptable to disable as hard filter, but should be flagged/reported. Recommend adding a PAINS *flag* (not filter) to compound output so users can see which compounds are PAINS-positive.

**QED Score (stored, not used in filter)**
- Bickerton et al. 2012 (Nature Chemistry) — drug-likeness 0–1 integrating MW, logP, HBD, HBA, PSA, rotbonds, aromatics, alerts
- Currently stored on compounds but not used as a filter criterion
- **Verdict**: Correct to store but not hard-filter. Best used as a *ranking* signal within passed compounds. Document this recommendation.

- [ ] Add docstring to `AdmeParams` in `backend/analysis/models.py`:

```python
@dataclass
class AdmeParams:
    """
    ADME screening parameters for compound filtering.

    Lipinski RO5 (Lipinski et al., Adv. Drug Deliv. Rev. 23:3-25, 1997):
      Empirical thresholds for oral bioavailability of drug-like molecules.
      Note: designed for synthetic compounds; many natural products violate RO5.
      NP exception (np_exception_threshold) compensates for this limitation.

    Veber rules (Veber et al., J. Med. Chem. 45:2615-2623, 2002):
      Additional oral permeability criteria based on TPSA and rotatable bonds.

    NP exception (Ertl & Schuffenhauer, J. Nat. Prod. 71:951-959, 2008):
      Compounds with NP-likeness score >= threshold bypass RO5/Veber filters.
      Threshold 0.5 captures compounds with strong natural-product character.

    PAINS (Baell & Holloway, J. Med. Chem. 53:2719-2740, 2010):
      Not applied as a hard filter (apply_pains=False); NP pipeline targets
      computational target prediction, not biochemical assay screening.
    """
    max_mw: float = 500.0
    max_logp: float = 5.0
    max_hbd: int = 5
    max_hba: int = 10
    max_tpsa: float = 140.0
    max_rotatable_bonds: int = 10
    apply_veber: bool = True
    apply_pains: bool = False   # unimplemented; reserved for future assay-based use
    np_exception_threshold: float = 0.5
```

- [ ] **Confirmation gate**: Present ADME methodology assessment to user — what is scientifically defensible as-is, what gaps exist, options + pros/cons for any changes. Wait for user approval before applying any code changes beyond the docstring.
- [ ] Commit: `docs(backend): add scientific citations and rationale to AdmeParams`

---

### Task P3-B: Validate PAINS Config is Harmless

- [ ] Confirm in `backend/analysis/stages/stage2_adme.py`: `apply_pains` is read from params but there is NO code path that uses it
- [ ] Verify: the field is not silently filtering anything (confirm by reading the `filter_compounds()` function in full)
- [ ] If confirmed no-op: no action needed on logic, only the docstring from P3-A is sufficient
- [ ] If found to be partially implemented and producing wrong results: fix or fully disable
- [ ] Document in `docs/data-audit-session/phase-3.md`

---

## Phase 4: Network Pharmacology Pipeline Review [xH]

**Goal:** Verify all 8 analysis stages are scientifically and methodologically sound.

**Dispatch 2 parallel subagents** (Stages 1-5 / Stages 6-8).

---

### Task P4-A: Stages 1–5 Review [xH]

**Files:** `stage1_selection.py`, `stage2_adme.py` (covered in Phase 3), `stage3_targets.py`, `stage4_disease_targets.py`, `stage5_overlap.py`, `backend/integrations/chembl.py`

#### Stage 1: Compound Selection

- [ ] Read `backend/analysis/stages/stage1_selection.py`
- [ ] Verify: compounds are selected by plant IDs (user selects plants → filter compounds via `plant_compounds` join)
- [ ] Check: is there any deduplication if the same compound appears in multiple selected plants? Should be deduped to unique compound_ids for downstream stages
- [ ] Note any issues; document in phase-4.md

#### Stage 3: ChEMBL Target Query

- [ ] Read `backend/analysis/stages/stage3_targets.py` + `backend/integrations/chembl.py`
- [ ] Find: what bioactivity endpoint is queried (IC50? Ki? All types?)
- [ ] Find: is `assay_confidence_score` filtered?
  - ChEMBL assay confidence scores: 9=direct/single protein, 8=direct, 7=functional, ≤6=indirect/cell/organism
  - For target identification in NP: score ≥ 7 is standard; ≥ 8 is conservative
- [ ] Find: is `target_organism` filtered to Homo sapiens (NCBI taxon 9606)?
  - Without species filter: cross-species targets inflate the compound-target set
  - For human disease network pharmacology: filter to human targets is standard
- [ ] **If missing confidence filter**: add `assay_confidence_score__gte=7` to ChEMBL bioactivity query
- [ ] **If missing species filter**: add `target_organism=Homo+sapiens` to ChEMBL query
- [ ] **Impact of adding filters**: Stage 3 returns fewer (but higher quality) targets → affects Stages 4-8 output
  - Not a schema change; data quality improvement
  - Document in phase-4.md under "Breaking Changes"
- [ ] **Confirmation gate**: If filters are missing, present to user — current behavior (unfiltered), impact of adding each filter (quality vs. coverage trade-off with example: adding `assay_confidence_score ≥ 7` reduces targets but removes indirect/cell-based assays), recommendation. Wait for approval before applying.
- [ ] Commit any fix: `fix(backend/stage3): add assay confidence and species filters to ChEMBL query`

#### Stage 4: Disease Target Sources

- [ ] Read `backend/analysis/stages/stage4_disease_targets.py`
- [ ] Verify: reads from `disease_targets` table (pre-loaded from Open Targets ETL) NOT live API
- [ ] Check: what `association_score` threshold is applied when querying DB?
  - Open Targets scores: 0.0-1.0; 0.5+ is "medium evidence"; 0.2+ includes "indirect"
  - Standard for network pharmacology: ≥ 0.2 to cast a wider net
- [ ] Check: **disease_id bug** — does Stage 4 correctly receive `disease_id` from the analysis run?
  - From previous session obs 1053-1056: `create_run()` ignores disease_id → `analysis_run.disease_id` is null → Stage 4 can't query the correct disease
  - This is a data pipeline bug, not just a display bug
  - Fix is in Phase 5 (P5-A Fix 2), but document the Stage 4 impact here
- [ ] Document findings in phase-4.md

#### Stage 5: Target Overlap Statistics

- [ ] Read `backend/analysis/stages/stage5_overlap.py` fully
- [ ] Verify Jaccard index formula: `|A ∩ B| / |A ∪ B|` where A = compound targets, B = disease targets
- [ ] Verify hypergeometric test:
  - Population M = total protein-coding genes (should be ~20,000 for Homo sapiens)
  - Find where M is defined — is it hardcoded or computed?
  - N = compound target set size, K = disease target set size, k = overlap
  - Test: `scipy.stats.hypergeom.sf(k-1, M, K, N)` or equivalent
- [ ] **Scientific note**: Using full genome as background (M ≈ 20,000) is standard (Huang et al., Nat. Protoc., 2009)
- [ ] Verify p-value is one-tailed (probability of overlap this large or larger by chance)
- [ ] Note: Jaccard is a similarity metric, not a significance test; both Jaccard + p-value together are the standard reporting for network pharmacology
- [ ] Document methodology with citations in phase-4.md
- [ ] Commit if corrections needed: `fix(backend/stage5): correct hypergeometric test background set`

---

### Task P4-B: Stages 6–8 Review [xH]

**Files:** `stage6_ppi.py`, `stage7_hub_genes.py`, `stage8_enrichment.py`, `backend/integrations/stringdb.py`, `backend/integrations/gprofiler.py`

#### Stage 6: STRING DB PPI Network

- [ ] Read `backend/analysis/stages/stage6_ppi.py` + `backend/integrations/stringdb.py`
- [ ] Verify parameters sent to STRING:
  - `identifiers`: list of gene symbols from Stage 5 overlap (correct input)
  - `species`: 9606 Homo sapiens (hardcoded — correct for human disease)
  - `required_score`: from `min_confidence` (default 0.4 → 400 in STRING's 0-1000 scale)
  - `caller_identity`: "herbaflow_thesis" — fine for rate limiting identification
- [ ] **Confidence threshold justification**:
  - 0.4 (medium confidence) is the most commonly used threshold in NP network pharmacology publications (e.g., Zhou et al., 2021 Nature Commun.; Tang et al., 2022)
  - 0.7 (high) is more conservative; 0.15 (low) is too noisy
  - **Verdict**: 0.4 is academically defensible; document the threshold choice
- [ ] Check: are isolated nodes (genes with no PPI edges after STRING filtering) removed from the network before Stage 7?
  - Isolated nodes have degree 0 and would rank last by all centrality metrics — harmless but noisy
  - Check if `stage7_hub_genes.py` filters them
- [ ] Document STRING parameter justification with citations in phase-4.md:
  - STRING paper: Szklarczyk et al., Nucleic Acids Res., 2023 (STRING v12)
  - Confidence levels: STRING documentation (https://string-db.org/cgi/info)

#### Stage 7: Hub Gene Ranking

- [ ] Read `backend/analysis/stages/stage7_hub_genes.py` fully
- [ ] Verify centrality metrics computed:
  - `degree_centrality`: connections / (N-1) — local connectivity
  - `betweenness_centrality`: fraction of shortest paths through node — bridge/bottleneck role
  - `closeness_centrality`: 1 / average distance to all others — proximity
  - `eigenvector_centrality`: influence based on neighbor quality
- [ ] Find final ranking logic: is it sorting by degree only? Weighted sum? Hub+bottleneck criterion?
  - **Hub+bottleneck criterion** (Jeong et al., Nature, 2001): a hub-bottleneck is a node with both high degree AND high betweenness
  - If implemented: document the threshold formula used
  - If NOT implemented (only sorting by degree): this is a significant omission — add hub+bottleneck composite score:
    ```python
    # Hub+bottleneck: normalize both metrics then combine
    df['hub_score'] = (
        0.5 * (df['degree_centrality'] / df['degree_centrality'].max()) +
        0.5 * (df['betweenness_centrality'] / df['betweenness_centrality'].max())
    )
    df = df.sort_values('hub_score', ascending=False)
    ```
- [ ] **Redundant fields**: `hub_genes` == `ranked` (same list); `threshold_degree` == `hub_degree_threshold` (same value)
  - Check frontend: `grep -r "hub_genes\|ranked\|threshold_degree\|hub_degree_threshold" frontend/src/`
  - Determine which field name frontend actually reads
  - Remove the unused duplicate field; keep the one frontend uses
- [ ] **Confirmation gate**: Present hub ranking methodology findings — current approach (degree-only or composite?), hub+bottleneck composite rationale (Jeong et al. 2001), impact on gene ranking results vs current output. Wait for user approval before applying changes.
- [ ] Commit any fixes: `fix(backend/stage7): implement hub+bottleneck composite score` and/or `refactor(backend/stage7): remove duplicate output fields`

#### Stage 8: g:Profiler Enrichment

- [ ] Read `backend/analysis/stages/stage8_enrichment.py` + `backend/integrations/gprofiler.py`
- [ ] Verify query gene list input: should be the hub genes from Stage 7 (`ranked` field, top N genes)
  - If it's only querying top 10-20 hub genes: the enrichment set may be too small
  - Standard: use top 10-30 hub genes OR all overlap genes (Stage 5 results) with hub genes as foreground
- [ ] Verify ontology sources queried: should include `GO:BP`, `GO:MF`, `GO:CC`, `KEGG`, optionally `REAC` (Reactome)
- [ ] Verify FDR correction: Benjamini-Hochberg (BH) is standard; g:Profiler uses `g_SCS` by default which is more conservative
  - `g_SCS` is g:Profiler's own correction method, more stringent than BH for multiple-ontology queries
  - **Verdict**: g_SCS is appropriate; document this choice
- [ ] Verify FDR threshold: < 0.05 is standard
- [ ] Verify **background gene set**: should be the set of all targets analyzed (full overlap + STRING network), NOT just all human genes
  - Using a custom background improves biological relevance of enrichment
  - Check if `background=None` (uses full genome) or custom background is passed
  - **If using full genome as background**: this may over-inflate significance — add custom background parameter
    ```python
    # background = all_compound_target_gene_symbols (Stage 3 output)
    ```
- [ ] Verify the **Stage 8 g:Profiler bug fix** from prior session (obs 1049) is in place:
  - Bug was: invalid API parameter causing silent zero-results
  - Check `gprofiler.py` for the fix — confirm correct parameter names in current code
- [ ] Document methodology with citations:
  - Raudvere et al., Nucleic Acids Res. 47:W191-W198, 2019 (g:Profiler)
- [ ] **Confirmation gate**: Present enrichment background findings — full genome vs custom background, how it affects p-values and term significance (custom background = more specific enrichment, fewer but more relevant terms), recommendation. Wait for user approval before applying.
- [ ] Commit: `fix(backend/stage8): use custom background gene set for enrichment` and/or `docs(backend/stage8): document enrichment methodology`

---

## Phase 5: Schema & Code Fixes [H]

**Goal:** Apply all structural fixes identified in Phases 0–4. Dispatch 2 parallel subagents.

---

### Task P5-A: Backend Model & Schema Fixes

**Files:**
- `backend/app/models/import_batch.py`
- `backend/app/repositories/analysis_repository.py`
- `backend/app/schemas/analysis.py`
- `frontend/src/types/api.ts` (if disease_id impact)
- `supabase/migrations/` (new migration for indexes)
- `.claude/docs/database.md`

#### Fix 1: ImportBatch.params Missing from ORM

- [ ] Read `backend/app/models/import_batch.py` in full
- [ ] Column `params` exists in DB (confirmed in Phase 0) but missing from SQLModel model
- [ ] Add field:
  ```python
  from typing import Any, Optional
  from sqlalchemy import Column, JSON
  from sqlmodel import Field, SQLModel
  
  class ImportBatch(SQLModel, table=True):
      # ... existing fields ...
      params: Optional[dict[str, Any]] = Field(
          default=None, sa_column=Column(JSON)
      )
  ```
- [ ] Verify: `python -c "from backend.app.models.import_batch import ImportBatch; print(ImportBatch.__fields__.keys())"` shows `params`
- [ ] Commit: `fix(backend): add missing params field to ImportBatch SQLModel`

#### Fix 2: disease_id Not Persisted in create_run()

- [ ] Read `backend/app/repositories/analysis_repository.py` — find `create_run()` method
- [ ] Find where `AnalysisRun` object is constructed — verify `disease_id` is accepted in the function signature but not passed to the model constructor
- [ ] Fix: pass `disease_id=disease_id` (or however it's named in the signature) to the `AnalysisRun(...)` constructor
- [ ] Read `backend/app/schemas/analysis.py` — find `AnalysisRunResponse`
- [ ] Add `disease_id: Optional[str] = None` to `AnalysisRunResponse` if missing
- [ ] **Frontend impact**: `GET /analyses` response now includes `disease_id` — additive, not breaking
  - Read `frontend/src/types/api.ts` — check `AnalysisRun` type
  - If missing `disease_id`: add `disease_id: string | null` to the TypeScript type
- [ ] Commit backend: `fix(backend): persist and expose disease_id in analysis create and response`
- [ ] Commit frontend type (if changed): `fix(frontend): add disease_id to AnalysisRun TypeScript type`

#### Fix 3: Add Missing Database Indexes

- [ ] Write `supabase/migrations/20260523000001_add_missing_indexes.sql`:
  ```sql
  -- Index for common target lookups
  CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_targets_uniprot
    ON targets(uniprot_accession);
  
  CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_targets_gene_symbol
    ON targets(gene_symbol);
  
  -- Index for analysis status filtering
  CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_analysis_runs_status
    ON analysis_runs(status);
  
  -- Index for disease-target score filtering
  CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_disease_targets_score
    ON disease_targets(score);
  ```
- [ ] Apply via Supabase MCP: `apply_migration` with the above SQL
- [ ] Update `.claude/docs/database.md` — add new indexes to the targets and analysis_runs table sections
- [ ] Commit: `perf(db): add missing indexes on targets, analysis_runs, disease_targets`

---

### Task P5-B: Code Quality Cleanup

**Files:**
- `backend/analysis/stages/stage7_hub_genes.py`
- `backend/analysis/models.py`
- `frontend/src/` (grep for hub_genes / ranked usage)

#### Fix 4: Stage 7 Duplicate Output Fields

- [ ] Run: `grep -r "hub_genes\|\.ranked\|threshold_degree\|hub_degree_threshold" frontend/src/` to find which names frontend uses
- [ ] Read `backend/analysis/stages/stage7_hub_genes.py` — identify the duplicate pairs:
  - `hub_genes` and `ranked` (same list of gene symbols)
  - `hub_degree_threshold` and `threshold_degree` (same float)
- [ ] Remove the field(s) frontend does NOT use
- [ ] If frontend uses both names for different purposes: this indicates a real distinction — do NOT remove; document instead
- [ ] Commit: `refactor(backend/stage7): remove duplicate hub_genes/threshold_degree fields from stage output`

#### Fix 5: Document apply_pains as No-op

- [ ] Read `backend/analysis/stages/stage2_adme.py` — confirm `apply_pains` is never checked in filter logic
- [ ] In `backend/analysis/models.py` AdmeParams: add inline comment to `apply_pains` field (already covered in P3-A docstring)
- [ ] Optionally: add a `# noqa: reserved` style note so it's clear this is intentional
- [ ] No commit needed if covered by P3-A commit

#### Fix 6: Stage 1 Compound Deduplication (if P4-A found issue)

- [ ] If Stage 1 does not deduplicate compounds appearing in multiple plants: add deduplication
  ```python
  # After joining plant_compounds, deduplicate by compound_id
  compound_ids = list({row.compound_id for row in results})
  ```
- [ ] Commit if needed: `fix(backend/stage1): deduplicate compounds appearing in multiple selected plants`

---

## Phase 6: Documentation Update [M]

**Goal:** All docs reflect current state. One pass at the end.

---

### Task P6-A: Update database.md

- [ ] Read `.claude/docs/database.md`
- [ ] Add new indexes from Fix 3 to the relevant table sections
- [ ] Verify `import_batches` table section includes `params` column (was already documented — confirm it matches after Fix 1)
- [ ] Add note: "All entity IDs (plant_id, compound_id, etc.) are bare UUID v5 (no prefix). Column name provides type context."
- [ ] Commit: `docs(database): update schema docs with index and ID convention notes`

---

### Task P6-B: data-audit-session Final Summary

- [ ] Write `docs/data-audit-session/phase-6.md` — master summary:
  - List of all confirmed issues from Phase 0 baseline
  - List of all fixes applied (phase, file, commit)
  - List of deferred items (e.g., ETL re-run needed after knapsack + family fixes)
  - Scientific/academic standing assessment per stage
  - Outstanding items (e.g., ETL pipeline re-run to clean DB data, PAINS future implementation)

---

### Task P6-C: ETL Re-run Recommendation

- [ ] Write `docs/data-audit-session/etl-rerun-checklist.md`:
  - Checklist for running the full ETL pipeline after code fixes to regenerate clean data
  - Order: knapsack → plants (all 6 stages) → compounds (all 7 stages) → load with `--upsert`
  - Note: diseases and disease_targets pipelines are unaffected by Phase 1-2 fixes
  - Note: after re-run, verify Phase 0 queries show: 0 duplicate plants, family_name null% ≈ 0
- [ ] Commit: `docs(etl): add ETL re-run checklist after audit fixes`

---

## Verification Checklist

After all phases and fixes are committed:

- [ ] `python -m pytest etl/tests/ -v` — all ETL tests pass
- [ ] `python -m pytest backend/tests/ -v` — all backend tests pass
- [ ] `GET /analyses` response includes `disease_id` field (curl or frontend check)
- [ ] Supabase MCP: re-run Phase 0 plant duplicate query → 0 duplicates after ETL re-run
- [ ] Supabase MCP: re-run Phase 0 family_name coverage query → near 0% null after ETL re-run
- [ ] Supabase MCP: `SELECT plant_id FROM plants LIMIT 1` — confirm bare UUID format (no prefix)
- [ ] Supabase MCP: confirm `uniprot_accession` index exists on targets table
- [ ] `backend/app/models/import_batch.py` has `params` field

---

## Commit Convention

All commits use Conventional Commits:
- `fix(scope): description` — bug fixes in logic or data
- `feat(scope): description` — new capabilities added
- `refactor(scope): description` — restructuring without behavior change
- `perf(scope): description` — performance improvements (indexes)
- `docs(scope): description` — documentation only

Scope examples: `etl/knapsack`, `etl/plants`, `etl/compounds`, `backend`, `backend/stage3`, `db`, `frontend`

---

## Parallelism Map

```
Phase 0: P0-A ─┐
               ├─ parallel (3 subagents)
Phase 0: P0-B ─┤
               │
Phase 0: P0-C ─┘
    ↓ (wait for all P0 results)
Phase 1: P1-A → P1-B → P1-C → P1-D (sequential within phase)
    ↓
Phase 2: P2-A ─┐
               ├─ parallel (2 subagents)
Phase 2: P2-B ─┘
    ↓
Phase 2: P2-C (depends on P2-B results)
    ↓
Phase 3: P3-A → P3-B (sequential)
    ↓
Phase 4: P4-A ─┐
               ├─ parallel (2 subagents)
Phase 4: P4-B ─┘
    ↓
Phase 5: P5-A ─┐
               ├─ parallel (2 subagents)
Phase 5: P5-B ─┘
    ↓
Phase 6: P6-A → P6-B → P6-C (sequential, fast)
```
