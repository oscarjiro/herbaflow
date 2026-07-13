# compounds ETL — Claude Conventions

## Pipeline Run Order

Run stages in this exact order after activating the ETL venv:

```powershell
python etl/compounds/main.py --start 1 --end 4   # extract → normalize → dedupe → enrich
python etl/compounds/04_enrich/patch_missing_smiles.py    # fill SMILES from cache / invalidate
python etl/compounds/04_enrich/patch_missing_lipinski.py  # fill ADME from ChEMBL + RDKit
python etl/compounds/main.py --start 5 --end 7   # build_canonical → validate → export
```

Or run the full pipeline then both patches if starting from scratch:

```powershell
python etl/compounds/main.py --start 1 --end 4
python etl/compounds/04_enrich/patch_missing_smiles.py
python etl/compounds/04_enrich/patch_missing_lipinski.py
python etl/compounds/main.py --start 5 --end 7
```

**Why patch before 05:** `05_build_canonical` reads `compound_enrichment_results.csv`
directly. Running patches after enrichment but before canonicalization ensures that
filled SMILES and Lipinski values propagate into the final `compounds.csv`.

## 04_enrich identity acceptance (corroboration gate)

A resolved PubChem/ChEMBL structure is accepted as the compound's identity ONLY when
corroborated. The decisive check is molecular-formula agreement: a correct resolution
preserves the raw KNApSAcK formula (compared Hill-normalized via
`shared.identity.formula_matches`). Accept paths:

- CAS synonym match AND formula agrees → `cas_formula_confirmed` (confidence 0.97)
- PubChem+ChEMBL agree on InChIKey AND formula agrees → `cross_source_confirmed` (0.97)
- strong name match AND formula agrees → `name_formula_confirmed` (0.90)

Everything else is REJECTED (structure fields left blank so 05 falls back to the raw
name_formula/name/cas identity, never a wrong InChIKey): `rejected_name_only`,
`rejected_formula_only`, `rejected_formula_mismatch`, `rejected_mw`,
`rejected_ambiguous_tie`, `rejected_uncorroborated` (all confidence 0.30, status
`review`). Salts/hydrates (`.`/`·` in the formula) never match a desalted formula.

`compound_enrichment_results.csv` now carries honest provenance for 05 to surface:
`match_strategy` (the values above), `evidence_type` (`cas+formula`, `name+formula`,
`cross_source+formula`, `name_only`, `formula_only`, `mw_only`, `cas_no_formula_confirm`,
`ambiguous`, `weak`, `none`), and an honest `enrichment_confidence` (high only when
structurally corroborated). `match_count` = distinct candidate structures; `match_rank`
= the accepted hit's rank (blank when rejected).

**Cache:** the raw HTTP cache (`out/cache/http/`) stays valid across logic changes, but
the per-candidate cache key folds `ENRICH_LOGIC_VERSION`, so bumping the acceptance logic
auto-recomputes `out/cache/candidates/` on the next run (delete it to force, keep http to
avoid re-fetching).

**Rate limits:** live requests honor PubChem PUG-REST limits (≤5/s, ≤400/min per IP) via a
process-wide `RateLimiter`, and back off on HTTP 429/503 respecting `Retry-After`. Tune via
`enrichment.pubchem.max_requests_per_second` / `max_requests_per_minute` in `settings.yml`.

**Per-candidate request budget:** a candidate that never corroborates would otherwise exhaust
every CAS/name term across PubChem+ChEMBL. `enrichment.max_requests_per_candidate` (default 8, `0`
disables) caps total requests per candidate; once spent, the search stops and the candidate is
rejected to `review` (the raw-identity fallback it reaches anyway). Corroborated candidates
early-exit at ~3-4 requests, well under the budget, so accepted structures are never affected.

**Smoke/sample run** (small live-API check before the full re-fetch):

```powershell
etl\.venv\Scripts\python.exe etl/compounds/04_enrich/run.py --limit 20
# or, through the orchestrator, via env var:
$env:ENRICH_LIMIT=20; etl\.venv\Scripts\python.exe etl/compounds/main.py --start 4 --end 4
```

## 05_build_canonical identity surfacing (no laundering, no salvage)

`05` consumes the honest enrichment verdict and surfaces it rather than hiding it:

- **Provenance columns on `compounds.csv`.** `match_strategy`, `evidence_type`, and
  `enrichment_confidence` are carried straight through from enrichment onto each
  canonical compound (and through `06_validate` → `07_export`), so a weak identity is
  visibly weak. `canonical_strategy` reads `inchi_key`/`pubchem_cid`/`chembl_id` only
  when enrichment ACCEPTED a corroborated structure.
- **Raw-identity fallback (no invented structure).** When enrichment rejected the
  structure (blank inchi_key/pubchem/chembl/formula), the compound falls back to its
  raw KNApSAcK identity via `shared.identity.compound_canonical_key`
  (`cas` → `name_formula` → `name` → `formula`) using member-consensus fields
  (`identity_view_for_candidate`). It is shipped as `provisional`, never dropped and
  never given a wrong InChIKey. `accepted` is reserved for a corroborated structure at
  or above the high-confidence threshold; genuinely identity-less candidates (no cas,
  name, or formula) are `unresolved`. The old `(source_name, identifier)` string-tiebreak
  salvage of conflicted enrichments is gone.
- **InChIKey-merge dedup preserved.** Two candidates resolving to the same real InChIKey
  still merge to one compound; the fallback extends the same merge to shared cas/name keys.
- **`plant_compounds.source_url`** is the KNApSAcK organism page
  `result.php?sname=organism&word=<URL-encoded species>` (via
  `shared.provenance.knapsack_organism_url`), which groups all metabolites of that
  organism. The species string is the KNApSAcK `organism` field, carried through
  `02_normalize` → `03_dedupe` members → `05`. Falls back to the per-metabolite page,
  then the base URL, when organism is absent.

## 06_validate formula-consistency guard

`06` adds a real correctness check on top of presence/format: for every compound with a
resolved structure (an InChIKey), the resolved `molecular_formula` must preserve the raw
KNApSAcK representative formula (Hill-normalized via `shared.identity.formula_matches`,
joined through `compound_candidate_map` → `compound_candidates.representative_formula`).
The corroboration gate in `04` should make this hold everywhere, so a mismatch is a
regression signal, reported as a `formula_mismatch_resolved_vs_raw` **warning** (it does
not fail the pipeline).

## 03_dedupe ambiguity

`03` clusters evidence by CAS+name+formula and does **not** attempt ambiguity resolution.
The former intra-cluster "conflict"/"ambiguous" detection tested distinctness of the very
field the cluster is keyed on, so it could never fire (measured: 0 ambiguous clusters) and
was removed. Real identity ambiguity is resolved downstream in `04` (a structure is
accepted only with corroboration). `03` still flags low-confidence and review-carrying
clusters as `review`. Members now carry the raw `organism` field through for `05`'s
`plant_compounds.source_url`.

## patch_missing_smiles.py

Run after `04_enrich/run.py` when any `smiles` fields are empty.
- Pass 1: mines existing candidate cache JSON for SMILES (zero API calls)
- Pass 2: invalidates candidate cache for still-missing rows → re-run `04_enrich/run.py`

After invalidation, re-run `04_enrich/run.py`. HTTP cache is preserved so only
invalidated candidates hit the enrichment logic.

## patch_missing_lipinski.py

Run after `patch_missing_smiles.py` when any `logp` fields are empty.
- Pass 1: fetches ChEMBL molecule detail by `chembl_id` (HTTP cache-first, zero cost if already cached)
- Pass 2: computes `MolLogP`, `NumHBD`, `NumHBA`, `TPSA`, `NumRotatableBonds` via RDKit from `smiles`
- Sets `lipinski_source` column: `chembl_api` | `rdkit_computed` | (empty = unresolved)

RDKit is installed in the ETL venv (`rdkit==2026.3.2`). No new dependencies needed.

Note: `qed_score` is only populated from ChEMBL (Pass 1); RDKit does not compute it.
`np_likeness_score` is populated from ChEMBL (Pass 1) or via RDKit NP scorer (Pass 2b,
using RDKit Contrib NP_Score/npscorer.py) for any row where it is still null but smiles
is present. Compounds with neither a `chembl_id` nor a usable `smiles` remain unresolved.

## Lipinski Coverage Baseline (as of May 2026)

After full enrichment + both patches:
- `molecular_weight`: 100% present (always fetched from PubChem)
- `logp` / `hbond_donors` / `hbond_acceptors` / `rotatable_bonds` / `tpsa`: ~47% populated
  from ChEMBL API; patches push this significantly higher
- Root cause of gaps: PubChem REST API provides structural data only (no ADME properties)

## Key Files

| File | Purpose |
|------|---------|
| `04_enrich/run.py` | Main enrichment (PubChem + ChEMBL identity resolution) |
| `04_enrich/patch_missing_smiles.py` | Post-enrichment SMILES recovery |
| `04_enrich/patch_missing_lipinski.py` | Post-enrichment ADME descriptor recovery |
| `05_build_canonical/run.py` | Canonical ID assignment, alias table, plant-compound bridge |

## Do Not Touch

- `04_enrich/out/cache/http/` — raw API response cache; delete only to force re-fetch
- `04_enrich/out/cache/candidates/` — per-candidate enrichment cache; delete individual
  files to re-process specific candidates (patch_missing_smiles.py does this automatically)
- Any `out/` directory — written by pipeline scripts only
