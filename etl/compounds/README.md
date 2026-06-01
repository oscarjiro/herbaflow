# compounds ETL Pipeline

Canonicalizes phytochemical metabolites from KNApSAcK Indonesia through PubChem and ChEMBL enrichment, producing a deduplicated, structure-annotated set of canonical compounds and plant-compound bridge records ready for PostgreSQL import.

This module is Step 3 in the Herbaflow ETL sequence:

```
knapsack/ → plants/ → compounds/ → diseases/ → disease_targets/
```

---

## Purpose in the Network Pharmacology Workflow

Network pharmacology maps the chemical space of Indonesian medicinal plants onto human disease biology by identifying target protein overlap between plant metabolites and disease-associated proteins. This module produces the compound side of that analysis.

Specifically, it:

1. Extracts raw metabolite evidence from KNApSAcK (plant_id, CAS, name, formula, MW)
2. Clusters duplicate evidence rows into unique compound candidates
3. Enriches each candidate against **PubChem** and **ChEMBL** to obtain stable chemical identifiers (InChIKey, SMILES, CID) and Lipinski druglikeness descriptors
4. Assigns a deterministic canonical identity and UUID to each compound
5. Produces the `plant_compounds` bridge table linking canonical plants (from `plants/`) to canonical compounds

Downstream, `disease_targets/` intersects compound targets (fetched via ChEMBL target associations from compound SMILES/CID) with disease-associated proteins to identify candidate therapeutic mechanisms.

---

## Data Sources

| Source             | URL                                       | Evidence provided                                                                                        | Authentication                       |
| ------------------ | ----------------------------------------- | -------------------------------------------------------------------------------------------------------- | ------------------------------------ |
| KNApSAcK Indonesia | https://www.knapsackfamily.com/KNApSAcK/  | Plant-compound occurrence, CAS ID, molecular formula, MW                                                 | None — scraped by `knapsack/` module |
| PubChem REST API   | https://pubchem.ncbi.nlm.nih.gov/rest/pug | Canonical name, InChIKey, SMILES, CID, Lipinski descriptors (TPSA, logP, HBD, HBA, rotatable bonds, QED) | None — public API                    |
| ChEMBL REST API    | https://www.ebi.ac.uk/chembl/api/data     | ChEMBL ID, synonyms, additional structure data                                                           | None — public API                    |

PubChem is the primary structure authority. ChEMBL supplements identity resolution and provides ChEMBL IDs used for downstream target lookups. All API responses are cached to disk — subsequent runs skip the network entirely.

---

## Pipeline Steps

### Step 1 — `01_extract/`

**Input:** `knapsack/out/plants_compounds.csv`, `plants/06_export/out/plants.csv`

**What it does:**

1. Reads the raw KNApSAcK output, which has one row per plant-compound occurrence
2. Validates that all expected raw columns are present (`plant_id`, `c_id`, `cas_id`, `metabolite`, `molecular_formula`, `mw`, `organism`)
3. Standardizes whitespace in all text fields — no other transformation
4. Resolves each raw `plant_id` to a canonical `plant_id` UUID using the finished plants ETL export
5. Attaches provenance metadata: `source_name`, `source_url`, `source_batch_id`, `retrieved_at`, `raw_row_hash`
6. Writes one output row per raw input row (no deduplication)

**Output:** `01_extract/out/plants_compounds_staged.csv`, `extract_compounds_manifest.json`

**Key columns in plants_compounds_staged.csv:**

| Column                 | Description                                                         |
| ---------------------- | ------------------------------------------------------------------- |
| `plant_id`             | Raw KNApSAcK plant identifier                                       |
| `c_id`                 | Raw KNApSAcK compound identifier                                    |
| `cas_id`               | CAS registry number as scraped (may contain formatting errors)      |
| `metabolite`           | Raw metabolite name from KNApSAcK                                   |
| `molecular_formula`    | Molecular formula string                                            |
| `mw`                   | Molecular weight string                                             |
| `canonical_plant_id`   | UUID from plants ETL (empty if unresolved)                          |
| `plant_mapping_status` | `mapped` or `unmapped`                                              |
| `raw_row_hash`         | SHA-256 of the full raw evidence payload — stable dedup fingerprint |

---

### Step 2 — `02_normalize/`

**Input:** `01_extract/out/plants_compounds_staged.csv`

**What it does:**

1. Normalizes metabolite names (whitespace collapse, Unicode normalization)
2. Normalizes CAS IDs: strips spaces, validates checksum digit, classifies as valid/invalid/missing
3. Canonicalizes molecular formula strings (removes spaces, preserves element order)
4. Formats molecular weights to 6 decimal places, then trims trailing zeros
5. Generates lookup keys (`to_key()`) for name, CAS, and formula — used by downstream matching
6. Flags rows as `ready` or `review` based on unresolved plant mapping, invalid CAS, or missing name
7. Emits a plant mapping resolution CSV and a review CSV for flagged rows

**Output:** `02_normalize/out/compounds_normalized.csv`, `plant_mapping_resolution.csv`, `compound_review.csv`, `normalize_compounds_summary.json`

**Key columns added by normalization:**

| Column                       | Description                                                |
| ---------------------------- | ---------------------------------------------------------- |
| `normalized_metabolite_name` | Whitespace-normalized metabolite name                      |
| `normalized_metabolite_key`  | Lowercased, punctuation-stripped lookup key                |
| `normalized_cas_id`          | Validated and reformatted CAS string                       |
| `cas_is_valid`               | `true`/`false` — checksum validation result                |
| `source_compound_key`        | SHA-256 of raw evidence fields — row fingerprint for dedup |
| `normalization_status`       | `ready` or `review`                                        |
| `review_reason`              | Semicolon-delimited list of review flags                   |

---

### Step 3 — `03_dedupe_candidates/`

**Input:** `02_normalize/out/compounds_normalized.csv`, `compound_review.csv`, `plant_mapping_resolution.csv`

**What it does:**

1. Merges normalized rows and review rows using `raw_row_hash` as a stable dedup key (review CSV is an overlay, not a duplicate source)
2. Re-resolves plant mappings from the resolution CSV as a second-pass improvement
3. Clusters evidence rows into unique compound candidates using a tiered signature strategy:
    - Tier 1 (confidence 0.985–0.99): valid CAS + name + formula
    - Tier 2 (confidence 0.80–0.88): name + formula + MW, or name + CAS
    - Tier 3 (confidence 0.50–0.78): formula + MW, name only, unverified CAS, formula only
    - Tier 4 (confidence 0.40): source row fingerprint (last resort)
4. Adjusts confidence based on evidence consistency (multi-member support, review penalties, inter-member conflicts)
5. Assigns `candidate_status`: `ready`, `review`, or `ambiguous`
6. Builds `compound_candidate_members.csv` linking each raw evidence row to its parent candidate

**Output:** `03_dedupe_candidates/out/compound_candidates.csv`, `compound_candidate_members.csv`, `compound_candidate_review.csv`, `dedupe_summary.json`

**Key columns in compound_candidates.csv:**

| Column                   | Description                                                              |
| ------------------------ | ------------------------------------------------------------------------ |
| `compound_candidate_id`  | SHA-256-derived hex ID (`cmpcand_{16 hex chars}`)                        |
| `candidate_key`          | Deterministic signature string encoding the clustering strategy          |
| `candidate_key_strategy` | Strategy name: `cas_exact_name_formula_support`, `name_formula_mw`, etc. |
| `representative_name`    | Most frequent name across member evidence rows                           |
| `representative_cas_id`  | Most frequent CAS across member evidence rows                            |
| `candidate_status`       | `ready`, `review`, or `ambiguous`                                        |
| `candidate_confidence`   | 0.0–1.0 adjusted confidence score                                        |
| `member_count`           | Number of raw evidence rows supporting this candidate                    |
| `search_terms_json`      | JSON array of all terms to submit to PubChem/ChEMBL                      |

---

### Step 4 — `04_enrich/`

**Input:** `03_dedupe_candidates/out/compound_candidates.csv`, `compound_candidate_members.csv`, `compound_candidate_review.csv`

**What it does:**

1. Queries PubChem REST API for each candidate using its `search_terms_json` (CAS, name, formula), with a cache-first strategy — responses are stored under `04_enrich/out/cache/`
2. Queries ChEMBL REST API to retrieve ChEMBL IDs and supplementary identity data
3. Scores each API hit deterministically: InChIKey match = 1.0, PubChem CID exact = 1.0, ChEMBL ID = 0.95, CAS match = 0.85, name-only = 0.60
4. Selects the best hit per candidate based on the scoring ladder; stores all ordered hits in the candidate cache JSON
5. Retrieves Lipinski descriptors for matched compounds: TPSA, logP, H-bond donors/acceptors, rotatable bonds, QED score, NP-likeness score, number of Ro5 violations
6. Writes one enrichment result row per compound candidate
7. Sends unresolvable candidates to `compound_enrichment_review.csv`

**Output:** `04_enrich/out/compound_enrichment_results.csv`, `compound_enrichment_cache.csv`, `compound_enrichment_member_map.csv`, `compound_enrichment_review.csv`, `enrich_summary.json`, `out/cache/*.json`

**Key columns in compound_enrichment_results.csv:**

| Column                  | Description                                     |
| ----------------------- | ----------------------------------------------- |
| `compound_candidate_id` | FK → compound_candidates                        |
| `inchi_key`             | Standard InChIKey from PubChem (27-char hash)   |
| `smiles`                | Canonical SMILES string                         |
| `pubchem_cid`           | PubChem Compound ID integer                     |
| `chembl_id`             | ChEMBL accession (e.g. `CHEMBL446858`)          |
| `molecular_weight`      | Exact molecular weight (g/mol)                  |
| `tpsa`                  | Topological polar surface area (A^2)            |
| `logp`                  | Octanol-water partition coefficient (XLogP3)    |
| `hbond_donors`          | Lipinski H-bond donor count                     |
| `hbond_acceptors`       | Lipinski H-bond acceptor count                  |
| `rotatable_bonds`       | Number of rotatable bonds                       |
| `qed_score`             | Quantitative estimate of drug-likeness (0–1)    |
| `np_likeness_score`     | Natural product likeness score                  |
| `num_ro5_violations`    | Number of Lipinski Rule of Five violations      |
| `match_confidence`      | Final hit confidence score (0.0–1.0)            |
| `cache_key`             | Lookup key into `compound_enrichment_cache.csv` |

**Caching behavior:** Each candidate produces a JSON file under `out/cache/`. On re-run, if the cache file exists the API is skipped. Delete individual cache files or the entire `out/cache/` directory to force re-enrichment. The `compound_enrichment_cache.csv` index maps `cache_key` to the file path.

---

### Step 4a — `04_enrich/patch_missing_smiles.py`

An operator tool for filling in SMILES strings missed by the main enrichment run without triggering a full re-run.

**When to use it:** After `04_enrich/run.py` completes and you notice that some compounds have empty `smiles` in `compound_enrichment_results.csv`.

**What it does (two phases):**

1. **FREE PASS** — for each missing-SMILES candidate, reads the existing candidate cache JSON and walks `ordered_hits` for any hit that already has a SMILES string. If found, patches `compound_enrichment_results.csv` in-place (zero API calls). Backs up originals before writing.
2. **INVALIDATE** — for candidates still missing SMILES after the free pass, deletes only the candidate-level cache file so `04_enrich/run.py` will re-process just those candidates. The HTTP cache (raw PubChem/ChEMBL responses) is left untouched — old lookups replay for free.

After running this tool, re-run `04_enrich/run.py` normally. Only the invalidated candidates hit the enrichment logic again.

```powershell
# Dry run to see what would happen
python etl/compounds/04_enrich/patch_missing_smiles.py --dry-run

# Actually patch
python etl/compounds/04_enrich/patch_missing_smiles.py
```

---

### Step 4b — `04_enrich/patch_missing_lipinski.py`

An operator tool for filling in missing Lipinski/ADME descriptors (`logp`, `tpsa`, `hbond_donors`, `hbond_acceptors`, `rotatable_bonds`) without re-running full enrichment.

**When to use it:** After `04_enrich/run.py` (and `patch_missing_smiles.py`) completes and you notice that some compounds have empty `logp` in `compound_enrichment_results.csv`. This is expected for PubChem-only hits — PubChem's REST API provides structural data only; ADME properties come exclusively from ChEMBL.

**Run order:** Always run `patch_missing_smiles.py` first. Having SMILES populated maximizes the number of compounds recoverable via the RDKit pass.

**What it does (two passes):**

1. **ChEMBL API pass** — for each missing-descriptor row with a `chembl_id`, fetches the ChEMBL molecule detail endpoint and extracts `molecule_properties`. Checks the existing HTTP cache first (zero API calls if the response was already cached during `04_enrich/run.py`). Backs up the original CSV before writing.
2. **RDKit pass** — for rows still missing after Pass 1 that have a non-empty `smiles`, computes `MolLogP`, `NumHBD`, `NumHBA`, `TPSA`, and `NumRotatableBonds` via RDKit. Note: `qed_score` and `np_likeness_score` are not computed by this pass.

Sets `lipinski_source` on each patched row: `chembl_api`, `rdkit_computed`, or empty (unresolved).

**Compounds that remain unresolved** after both passes have neither a `chembl_id` nor a usable `smiles` — these are typically highly provisional records from KNApSAcK with incomplete structural information.

```powershell
# Dry run to see what would happen
python etl/compounds/04_enrich/patch_missing_lipinski.py --dry-run

# Apply both passes
python etl/compounds/04_enrich/patch_missing_lipinski.py

# ChEMBL API only (skip RDKit)
python etl/compounds/04_enrich/patch_missing_lipinski.py --no-rdkit
```

---

### Step 5 — `05_build_canonical/`

**Input:** `04_enrich/out/compound_enrichment_results.csv`, `compound_enrichment_member_map.csv`, `compound_enrichment_review.csv`, `03_dedupe_candidates/out/compound_candidates.csv`, `compound_candidate_members.csv`

**What it does:**

1. Selects the final canonical identity per compound, using the enrichment winner; salvages ambiguous/review candidates when identity evidence is strong enough (InChIKey or PubChem CID present)
2. Assigns `canonical_status`: `accepted` (enrichment fully matched), `provisional` (identity resolved with caveats), `review` (uncertain), `unresolved` (no usable identity)
3. Generates deterministic UUID v5 `compound_id` using namespace `herbaflow.compounds`, keyed on the InChIKey or best available canonical key
4. Generates `compound_aliases.csv`: one alias row per name, synonym, CAS ID, and identifier variant; aggressively deduplicated
5. Joins member evidence back through candidate membership to produce `plant_compounds.csv` — the many-to-many bridge between `plant_id` and `compound_id`
6. Writes `compound_review.csv` for the 8 unresolved candidates requiring manual inspection

**Output:** `05_build_canonical/out/compounds.csv`, `compound_aliases.csv`, `plant_compounds.csv`, `compound_review.csv`, `build_canonical_summary.json`

---

### Step 6 — `06_validate/`

**Input:** `05_build_canonical/out/` (all output files)

**Checks performed:**

| Check type                | Description                                                        |
| ------------------------- | ------------------------------------------------------------------ |
| Required columns present  | All schema columns in each output file                             |
| No duplicate primary keys | `compound_id`, `compound_alias_id`, `plant_compound_id` all unique |
| No orphan plant links     | All `plant_id` in `plant_compounds` exist in the plants ETL export |
| No orphan compound links  | All `compound_id` in `plant_compounds` exist in `compounds.csv`    |
| CAS format validity       | Flags malformed CAS strings as `invalid_cas_format` warnings       |
| Unresolved candidates     | Warns if any candidates could not be resolved                      |
| High provisional ratio    | Warns if provisional compounds are an unusually large fraction     |

All check failures that are structural (missing columns, duplicate PKs, orphan FKs) exit with code 1. CAS format issues and provisional ratio are warnings only and do not halt the pipeline.

**Output:** `06_validate/out/validation_report.json`

---

### Step 7 — `07_export/`

**Input:** `06_validate/out/` (validated outputs, pass-through copy)

**What it does:** Copies all canonical CSV files to `07_export/out/` and writes `export_manifest.json` with row counts, column lists, paths, and run metadata. Also carries forward the `validation_report.json` and `validation_counts.csv` into the export directory for archival.

**Output:** `07_export/out/compounds.csv`, `compound_aliases.csv`, `plant_compounds.csv`, `compound_candidate_map.csv`, `compound_review.csv`, `plant_compound_review.csv`, `export_manifest.json`

These are the files used for PostgreSQL import.

---

## Output Schema Reference

### `compounds.csv` (11,305 rows)

Matches the `compounds` database table.

| Column               | Type     | Description                                                                                                               |
| -------------------- | -------- | ------------------------------------------------------------------------------------------------------------------------- |
| `compound_id`        | UUID v5  | Primary key — deterministic from the compound's InChIKey or best canonical key, using namespace `herbaflow.compounds`     |
| `canonical_key`      | text     | `inchi::{InChIKey}` — unique chemical identity key used to derive the UUID                                                |
| `canonical_name`     | text     | Preferred IUPAC or common name (PubChem preferred over ChEMBL over KNApSAcK)                                              |
| `inchi_key`          | text     | Standard 27-character InChIKey (e.g., `VHBFFQKBGNRLFZ-UHFFFAOYSA-N`)                                                      |
| `smiles`             | text     | Canonical SMILES string from PubChem                                                                                      |
| `cas_id`             | text     | Best available CAS registry number; may be empty if not resolved                                                          |
| `pubchem_cid`        | text     | PubChem Compound ID integer                                                                                               |
| `chembl_id`          | text     | ChEMBL accession (e.g., `CHEMBL446858`); empty if not found in ChEMBL                                                     |
| `molecular_formula`  | text     | Hill-notation molecular formula (e.g., `C21H20O12`)                                                                       |
| `molecular_weight`   | float    | Exact molecular weight in g/mol                                                                                           |
| `tpsa`               | float    | Topological polar surface area (A^2) — proxy for membrane permeability; <140 A^2 indicates oral bioavailability potential |
| `logp`               | float    | XLogP3 octanol-water partition coefficient — lipophilicity; Lipinski limit: ≤5                                            |
| `hbond_donors`       | int      | Lipinski H-bond donor count (NH + OH groups); limit: ≤5                                                                   |
| `hbond_acceptors`    | int      | Lipinski H-bond acceptor count (N + O atoms); limit: ≤10                                                                  |
| `rotatable_bonds`    | int      | Number of rotatable single bonds — flexibility proxy                                                                      |
| `qed_score`          | float    | Quantitative estimate of drug-likeness (0–1); >0.6 considered drug-like                                                   |
| `np_likeness_score`  | float    | Natural product likeness score (negative = less NP-like, positive = more NP-like)                                         |
| `num_ro5_violations` | int      | Number of Lipinski Rule of Five violations (0 = fully compliant)                                                          |
| `lipinski_source`    | text     | How ADME descriptors were obtained: `chembl_api`, `rdkit_computed`, or empty (unresolved)                                 |
| `source_name`        | text     | `PubChem` (primary enrichment source)                                                                                     |
| `source_url`         | text     | PubChem compound page URL                                                                                                 |
| `source_batch_id`    | text     | Run ID timestamp of the enrichment run                                                                                    |
| `retrieved_at`       | ISO 8601 | UTC timestamp of enrichment                                                                                               |
| `confidence`         | float    | Final match confidence (0.0–1.0)                                                                                          |
| `canonical_status`   | text     | `accepted`, `provisional`, `review`, or `unresolved`                                                                      |
| `canonical_strategy` | text     | Matching strategy used: `inchi_key`, `pubchem_cid_only`, `chembl_id_only`, etc.                                           |
| `canonical_reason`   | text     | Pipe-delimited evidence chain explaining the canonical decision                                                           |
| `evidence_count`     | int      | Number of raw KNApSAcK evidence rows supporting this compound                                                             |
| `plant_count`        | int      | Number of distinct canonical plants this compound is linked to                                                            |

**UUID derivation:** `compound_id = uuid5(uuid5(DNS, "herbaflow.compounds"), canonical_key)`. For compounds with an InChIKey, `canonical_key = "inchi::{InChIKey}"`. Given the same InChIKey, the same UUID is always produced — re-running the pipeline never changes existing IDs.

**Lipinski descriptors:** The four classic Lipinski Ro5 properties (`molecular_weight`, `logp`, `hbond_donors`, `hbond_acceptors`) describe oral bioavailability potential. In network pharmacology, compounds with 0 violations (`num_ro5_violations = 0`) are prioritized as candidate drug-like leads. `tpsa` and `rotatable_bonds` extend the profile with absorption and conformational flexibility data. `qed_score` provides a composite drug-likeness estimate on a 0–1 scale.

### `compound_aliases.csv` (73,469 rows)

Matches the `compound_aliases` database table.

| Column              | Type     | Description                                                                            |
| ------------------- | -------- | -------------------------------------------------------------------------------------- |
| `compound_alias_id` | UUID v5  | Deterministic from `(compound_id, alias_name)`, namespace `herbaflow.compound_aliases` |
| `compound_id`       | UUID v5  | FK → compounds                                                                         |
| `alias_name`        | text     | The alias string (name, synonym, CAS, InChIKey, etc.)                                  |
| `alias_key`         | text     | Lowercased, whitespace-collapsed lookup key                                            |
| `alias_type`        | text     | `iupac_name`, `common_name`, `cas_id`, `inchi_key`, `smiles`, `pubchem_synonym`, etc.  |
| `source_name`       | text     | Source that provided this alias                                                        |
| `source_url`        | text     | PubChem or ChEMBL URL                                                                  |
| `source_batch_id`   | text     | Run ID                                                                                 |
| `retrieved_at`      | ISO 8601 | UTC timestamp                                                                          |

### `plant_compounds.csv` (20,891 rows)

Matches the `plant_compounds` database table. One row per canonical plant-compound occurrence.

| Column                   | Type     | Description                                                          |
| ------------------------ | -------- | -------------------------------------------------------------------- |
| `plant_compound_id`      | UUID v5  | Deterministic from `(plant_id, compound_id)` pair grain              |
| `plant_id`               | UUID v5  | FK → plants                                                          |
| `compound_id`            | UUID v5  | FK → compounds                                                       |
| `source_name`            | text     | `KNApSAcK`                                                           |
| `retrieved_at`           | ISO 8601 | UTC timestamp                                                        |

### `compound_candidate_map.csv` (12,593 rows)

Audit table mapping each raw compound candidate to its resolved canonical compound. Useful for tracing how a raw KNApSAcK entry became a canonical compound record.

### `compound_review.csv` (8 rows)

Candidates that could not be resolved to a canonical compound identity. Each row has an `issue_type` and `issue_reason` explaining why resolution failed. These require manual inspection before they can be added to the canonical set.

---

## Configuration (`settings.yml`)

| Key                                                            | Default                                              | Description                                                        |
| -------------------------------------------------------------- | ---------------------------------------------------- | ------------------------------------------------------------------ |
| `source.name`                                                  | `KNApSAcK`                                           | Display name written to all output records                         |
| `source.url`                                                   | `https://www.knapsackfamily.com/KNApSAcK/`           | Source URL written to output records                               |
| `source.batch_id`                                              | `auto`                                               | Run ID; `auto` generates a timestamp-based ID at runtime           |
| `paths.raw.plants_compounds_csv`                               | `knapsack/out/plants_compounds.csv`                  | Raw KNApSAcK input (relative to `etl/`)                            |
| `paths.plant_etl.canonical_plants_csv`                         | `plants/06_export/out/plants.csv`                    | Upstream plants ETL output used for plant ID resolution            |
| `paths.plant_etl.plant_aliases_csv`                            | `plants/06_export/out/plant_aliases.csv`             | Plant alias table (supplementary resolution)                       |
| `enrichment.pubchem.base_url`                                  | `https://pubchem.ncbi.nlm.nih.gov/rest/pug`          | PubChem REST API base URL                                          |
| `enrichment.pubchem.timeout_seconds`                           | `30`                                                 | Per-request timeout                                                |
| `enrichment.pubchem.max_retries`                               | `4`                                                  | Retries on network error                                           |
| `enrichment.pubchem.request_delay_seconds`                     | `0.3`                                                | Delay between requests (rate limiting)                             |
| `enrichment.pubchem.cache_responses`                           | `true`                                               | Cache API responses to disk                                        |
| `enrichment.chembl.base_url`                                   | `https://www.ebi.ac.uk/chembl/api/data`              | ChEMBL REST API base URL                                           |
| `enrichment.chembl.timeout_seconds`                            | `30`                                                 | Per-request timeout                                                |
| `enrichment.chembl.max_retries`                                | `4`                                                  | Retries on network error                                           |
| `enrichment.chembl.request_delay_seconds`                      | `0.3`                                                | Delay between requests                                             |
| `enrichment.chembl.cache_responses`                            | `true`                                               | Cache API responses to disk                                        |
| `matching.high_confidence_threshold`                           | `0.90`                                               | Confidence at or above which a candidate is auto-accepted          |
| `matching.medium_confidence_threshold`                         | `0.70`                                               | Confidence at or above which a candidate proceeds without review   |
| `matching.review_confidence_threshold`                         | `0.50`                                               | Below this, candidate goes to review queue                         |
| `matching.pubchem_cid_exact_match_weight`                      | `1.0`                                                | Confidence weight for exact PubChem CID match                      |
| `matching.inchikey_exact_match_weight`                         | `1.0`                                                | Confidence weight for exact InChIKey match                         |
| `matching.chembl_id_exact_match_weight`                        | `0.95`                                               | Confidence weight for exact ChEMBL ID match                        |
| `matching.cas_exact_match_weight`                              | `0.85`                                               | Confidence weight for exact CAS match                              |
| `matching.name_only_match_weight`                              | `0.60`                                               | Confidence weight for name-only match                              |
| `matching.deduplicate_by`                                      | `[inchikey, pubchem_cid, chembl_id, canonical_name]` | Deduplication priority order                                       |
| `validation.thresholds.min_compound_confidence_to_auto_accept` | `0.70`                                               | Minimum confidence for automatic canonical acceptance              |
| `validation.thresholds.max_orphan_plant_join_ratio`            | `0.00`                                               | Fail if any plant-compound rows reference non-existent plants      |
| `validation.thresholds.max_missing_identifier_ratio`           | `0.20`                                               | Warn if >20% of compounds have no chemical identifier              |
| `validation.checks.allow_review_queue`                         | `true`                                               | Whether unresolved candidates may exist without failing validation |
| `export.format`                                                | `csv`                                                | Output format (CSV only currently)                                 |
| `sql_export.enabled`                                           | `false`                                              | SQL INSERT/UPSERT export (disabled by default)                     |

---

## How to Run

**Prerequisites:** Activate the ETL virtual environment first.

```powershell
# From repo root
etl\.venv\Scripts\Activate.ps1
```

**Full pipeline (all 7 stages):**

```powershell
python etl/compounds/main.py
```

**Single stage or range:**

```powershell
python etl/compounds/main.py --start 1 --end 1   # extract only
python etl/compounds/main.py --start 4 --end 4   # enrich only (reads from cache)
python etl/compounds/main.py --start 5 --end 7   # build_canonical → validate → export
```

**Dry run (print stage commands without executing):**

```powershell
python etl/compounds/main.py --dry-run
```

**Bypass enrichment cache (force re-fetch from PubChem/ChEMBL):**

```powershell
# Delete the entire cache directory
Remove-Item etl\compounds\04_enrich\out\cache\* -Recurse -Force
python etl/compounds/main.py --start 4 --end 7
```

**Patch missing SMILES and Lipinski descriptors (run after 04_enrich, before 05_build_canonical):**

```powershell
# Step 1: Fill missing SMILES from cache; invalidate remaining for re-enrichment
python etl/compounds/04_enrich/patch_missing_smiles.py --dry-run   # preview
python etl/compounds/04_enrich/patch_missing_smiles.py

# Step 2: If patch_missing_smiles invalidated any rows, re-run enrichment first
python etl/compounds/main.py --start 4 --end 4

# Step 3: Fill missing Lipinski/ADME descriptors via ChEMBL API + RDKit
python etl/compounds/04_enrich/patch_missing_lipinski.py --dry-run  # preview
python etl/compounds/04_enrich/patch_missing_lipinski.py

# Step 4: Continue with canonicalization and export
python etl/compounds/main.py --start 5 --end 7
```

**Unit tests:**

```powershell
python -m pytest etl/tests/ -v
```

---

## Output Interpretation

### `export_manifest.json`

```json
{
    "module": "compounds",
    "run_id": "compounds_20260516_210359",
    "summary": {
        "compounds_row_count": 11305,
        "compound_aliases_row_count": 73469,
        "plant_compounds_row_count": 20891,
        "compound_candidate_map_row_count": 12593,
        "compound_review_row_count": 8,
        "plant_compound_review_row_count": 237
    },
    "generated_at": "2026-05-16T21:03:59.767526+00:00"
}
```

Expected ranges for a full KNApSAcK Indonesia dataset:

- **compounds**: 10,000–14,000 (unique canonical compounds after deduplication)
- **compound_aliases**: 60,000–90,000 (several aliases per compound on average)
- **plant_compounds**: 18,000–25,000 (many-to-many bridge; one row per occurrence)
- **compound_review**: 0–20 (unresolved; should be small; investigate if >50)

### `validation_report.json`

Top-level fields:

| Field                  | Description                                                                                 |
| ---------------------- | ------------------------------------------------------------------------------------------- |
| `pass`                 | `true` if no critical errors; pipeline may continue                                         |
| `critical_error_count` | Count of FAIL-level checks; must be 0 for export to proceed                                 |
| `warning_count`        | Count of WARN-level issues; non-blocking                                                    |
| `issue_type_counts`    | Breakdown by issue type                                                                     |
| `table_counts`         | Per-file row count, unique ID count, issue count                                            |
| `warnings`             | Array of individual warning objects with `issue_type`, `issue_reason`, and `row_identifier` |

Current run (2026-05-16): `pass: true`, 0 critical errors, 17 warnings (15 `invalid_cas_format`, 1 `unresolved_candidates_present`, 1 `high_provisional_ratio`). All warnings are non-blocking.

**Warning types explained:**

| Warning type                    | Meaning                                                                                    | Action                                                                                                  |
| ------------------------------- | ------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------------------------- |
| `invalid_cas_format`            | CAS string does not match the standard `NNNNNNN-NN-N` format with valid checksum           | Low priority; CAS from KNApSAcK is often poorly formatted; compound is still resolved via InChIKey/name |
| `unresolved_candidates_present` | N candidates could not be matched to any chemical identity                                 | Review `compound_review.csv` to decide if manual resolution is needed                                   |
| `high_provisional_ratio`        | Provisional compounds (identity resolved but with caveats) are an unusually large fraction | Expected for natural product databases with sparse structural data; not an error                        |

### Spot-checking known compounds

After a successful run, verify expected biological compounds are present with correct identifiers:

```python
import pandas as pd

cmpd = pd.read_csv("etl/compounds/07_export/out/compounds.csv")
pc = pd.read_csv("etl/compounds/07_export/out/plant_compounds.csv")

# Curcumin — should be present, PubChem CID 969516
curcumin = cmpd[cmpd["canonical_name"].str.contains("curcumin", case=False, na=False)]
print(curcumin[["canonical_name", "pubchem_cid", "inchi_key", "num_ro5_violations", "qed_score"]])

# Check how many plants curcumin appears in
curcumin_id = curcumin["compound_id"].iloc[0]
curcumin_plants = pc[pc["compound_id"] == curcumin_id]
print(f"Curcumin appears in {len(curcumin_plants)} plant records")

# Summary of canonical_status distribution
print(cmpd["canonical_status"].value_counts())
# Expected: provisional ~9000, accepted ~2000, review/unresolved <20
```

---

## Idempotency

The pipeline is safe to re-run:

- **01_extract – 03_dedupe_candidates**: deterministic from input — same input always produces identical output. No external calls.
- **04_enrich**: reads from `out/cache/` by default — no redundant API calls as long as cache files exist. Cache hits are served in microseconds.
- **05_build_canonical – 07_export**: overwrite `out/` files deterministically — same enrichment results always produce the same canonical IDs.
- **UUID v5 IDs are stable**: re-running never changes existing `compound_id`, `compound_alias_id`, or `plant_compound_id` values — FK integrity in PostgreSQL is preserved across incremental loads.

To force a complete re-enrichment (e.g., to capture new PubChem data):

```powershell
Remove-Item etl\compounds\04_enrich\out\cache\* -Recurse -Force
python etl/compounds/main.py --start 4 --end 7
```

To reset the entire pipeline from scratch:

```powershell
1..7 | ForEach-Object {
    $d = "0$_"
    Remove-Item "etl\compounds\0${_}_*\out\*" -Recurse -Force -ErrorAction SilentlyContinue
}
python etl/compounds/main.py
```
