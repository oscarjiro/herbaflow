# Phase 0: Live Database Baseline

> Audit date: 2026-05-24  
> Supabase project: `npgnamokytghhgvzbysu` (herbaflow, ap-northeast-1)  
> All queries run via Supabase MCP (read-only).

---

## Table Row Counts

| Table | Rows |
|---|---|
| compound_aliases | 73,469 |
| target_aliases | 22,747 |
| plant_compounds | 20,891 |
| disease_targets | 14,736 |
| compounds | 11,305 |
| targets | 7,824 |
| plant_aliases | 597 |
| compound_targets | 524 |
| plants | 519 |
| analysis_runs | 87 |
| disease_aliases | 48 |
| target_rankings | 43 |
| diseases | 10 |
| source_systems | 7 |
| import_batches | 7 |
| analysis_run_plants | 0 |
| analysis_run_compounds | 0 |
| analysis_run_targets | 0 |
| analysis_run_diseases | 0 |
| analysis_run_ppi_edges | 0 |
| ppi_edges | 0 |
| pathways | 0 |
| target_pathways | 0 |

---

## P0-A: Plant Table

### Duplicates

**19 species** have exactly 2 rows each:

| Species |
|---|
| Boesenbergia rotunda (L.) Mansf. |
| Syzygium aromaticum (L.) Merr. & L.M.Perry |
| Curcuma longa L. |
| Erythrina subumbrans (Hassk.) Merr. |
| Catharanthus roseus (L.) G.Don |
| Paederia foetida L. |
| Manihot esculenta Crantz |
| Kalanchoe pinnata (Lam.) Pers. |
| Artocarpus altilis (Parkinson) Fosberg |
| Plumeria rubra L. |
| Senna alata (L.) Roxb. |
| Senna tora (L.) Roxb. |
| Tabernaemontana divaricata (L.) R.Br. ex Roem. & Schult. |
| Moringa oleifera Lam. |
| Tinospora crispa (L.) Miers ex Hook.fil. & Thomson |
| Cinnamomum verum J.Presl |
| Persea americana Mill. |
| Coffea canephora Pierre ex A.Froehner |
| Camellia sinensis (L.) Kuntze |

**Scope larger than expected**: Known issue was Curcuma longa only; actual scope is 19 species × 2 = 38 affected rows.

### family_name Coverage

| total | with_family (non-null) | missing_family (null or '') |
|---|---|---|
| 519 | 519 | 519 |

**Interpretation**: `COUNT(family_name) = 519` means all values are non-null. `missing_family = 519` means all values are empty string `''`. Conclusion: **family_name is '' (empty string) for ALL 519 plants**. Field is present but blank — the GBIF family propagation is broken.

### ID Format

Sample: `pl_9c6a391ec298dd0dee69a29c`  
**Format: `pl_` prefix + 24 hex chars** (NOT standard UUID format, NOT bare UUID v5).  
This contradicts ETL CLAUDE.md which documents "No prefixes — bare UUID v5". See P1-D for full investigation.

### Curcuma longa Detail

| plant_id | gbif_usage_key | confidence | compound_count |
|---|---|---|---|
| pl_b0133f9d541a67e77134345d | 2757624 | 99 | 180 |
| pl_bf36045f554639d9e1a91fda | 2757626 | 98 | 1 |

Two different GBIF usage keys → two different IDs → two DB rows. The second row (1 compound, confidence 98) is the orphan.

---

## P0-B: Compound Table

### ADME Coverage by lipinski_source

| lipinski_source | total | has_mw | has_logp | has_tpsa | has_hbd | has_hba | has_rotb | has_qed | has_np | has_smiles | has_inchikey |
|---|---|---|---|---|---|---|---|---|---|---|---|
| rdkit_computed | 5,962 | 5,962 | 5,962 | 5,962 | 5,962 | 5,962 | 5,962 | **0** | **0** | 5,962 | 5,962 |
| null (ChEMBL) | 5,343 | 5,343 | 5,335 | 5,335 | 5,335 | 5,335 | 5,335 | 5,335 | 5,335 | 5,343 | 5,343 |

**Critical finding**: 
- The `rdkit_computed` group (5,962 compounds) has **zero** `qed_score` and **zero** `np_likeness_score`.  
- Overall `np_likeness_score` null rate: 5,962 / 11,305 = **52.7%** — far above the 20% threshold.  
- The NP exception pathway in Stage 2 ADME is **blind for 52.7% of compounds**: they cannot benefit from the NP exception even if they are natural products.  
- Action required (P2-B): add RDKit NP-likeness score computation to `patch_missing_lipinski.py`.

Also noted: 8 compounds in the ChEMBL group are missing logp/tpsa/hbd/hba/rotb (5,343 − 5,335 = 8).

### Compound Name Canonicality (all-caps sample)

All sampled all-caps compounds have non-null `chembl_id` and empty `pubchem_cid`. Examples: BUTANOL (CHEMBL45462), EUROSTOSIDE (CHEMBL1080020), DENTATIN (CHEMBL552132), GUANOSINE (CHEMBL375655), CAMPHENE (CHEMBL2268550).

**Verdict**: All-caps names are ChEMBL `pref_name` values (ChEMBL convention for small molecules). **Not a bug.**

### Alias Type Distribution

| alias_type | count |
|---|---|
| enrichment_synonym | 30,036 |
| source_compound_id | 12,424 |
| cas_id | 12,391 |
| canonical_name | 11,015 |
| raw_metabolite_name | 4,213 |
| iupac_name | 3,390 |

Note: `chembl_id` and `pubchem_cid` are stored directly on the compounds table (not as alias rows). Alias coverage is broad.

### Zero-Alias Compounds

**0 compounds have zero aliases.** All compounds have at least one alias. Alias completeness is good.

---

## P0-C: Schema Health

### Target Coverage

| total | has_uniprot | has_gene_symbol | has_protein_name |
|---|---|---|---|
| 7,824 | 7,824 (100%) | 7,824 (100%) | 7,589 (97.0%) |

Excellent. All targets have UniProt accession and gene symbol.

### Disease Ontology Coverage

| ontology_source | count |
|---|---|
| Disease Ontology | 10 |

Only 10 diseases total. This reflects the current scope (small pilot dataset). Not a bug.

### analysis_runs: disease_id

| total | with_disease_id |
|---|---|
| 87 | **0** |

**Confirmed bug**: `disease_id` is NEVER persisted across all 87 analysis runs. Stage 4 (disease target query) is fundamentally broken — it cannot query the correct disease. Fix in P5-A Fix 2.

### ImportBatch Schema (DB)

| column | type | nullable |
|---|---|---|
| batch_id | uuid | NO |
| step_name | text | YES |
| status | text | YES |
| started_at | timestamptz | YES |
| finished_at | timestamptz | YES |
| params | **jsonb** | YES |
| log_path | text | YES |

`params` column **exists in DB** as `jsonb`. ORM model missing this field → Fix 1 in P5-A.  
Also note: `log_path` column exists in DB — check if ORM model includes it (adjacent finding).

### Indexes

**Already exist (no action needed):**
- `targets_uniprot_accession_idx` ✓
- `targets_gene_symbol_idx` ✓
- `targets_canonical_key_idx` + unique ✓
- `compounds_canonical_key_idx`, `compounds_chembl_id_idx`, `compounds_inchi_key_idx`, `compounds_pubchem_cid_idx` ✓
- `disease_targets_disease_id_idx`, `disease_targets_target_id_idx` ✓

**Missing (Fix 3 in P5-A):**
- `idx_analysis_runs_status` — missing; needed for status-filtered queries
- `idx_disease_targets_score` — missing; needed for association score threshold filtering

---

## ID Format Summary

| entity | sample | format |
|---|---|---|
| plant_id | `pl_9c6a391ec298dd0dee69a29c` | `pl_` + 24 hex |
| compound_id | `c4454692-818d-5031-9048-3c5c415769b4` | bare UUID (with dashes) |
| disease_target_id | `4ee0b6b4-9efc-5922-aedd-c5db495b57b4` | bare UUID (with dashes) |
| target_id | TBD (P1-D) | — |

Plant IDs use `pl_` prefix + non-standard hex length (24 chars, not 32). Compound/disease_target IDs use standard UUID format without prefix. **Inconsistency confirmed.** Investigate in P1-D.

---

## Confirmed Issues

| # | Issue | Severity | Action |
|---|---|---|---|
| 1 | 19 plant species duplicated | High | P1-A, P1-B |
| 2 | family_name = '' for all 519 plants | High | P1-C |
| 3 | plant_id format `pl_` prefix inconsistent with bare UUID compounds | Medium | P1-D |
| 4 | np_likeness_score null for 52.7% compounds | High | P2-B |
| 5 | disease_id never persisted (87/87 runs affected) | High | P5-A Fix 2 |
| 6 | ImportBatch.params missing from ORM | Medium | P5-A Fix 1 |
| 7 | analysis_runs missing status index | Low | P5-A Fix 3 |
| 8 | disease_targets missing score index | Low | P5-A Fix 3 |
| 9 | All-caps compound names | Not a bug | P2-A (documented) |
| 10 | ImportBatch.log_path may also be missing from ORM | Low | P5-A Fix 1 (check) |
