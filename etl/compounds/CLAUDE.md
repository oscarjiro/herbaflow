# compounds ETL — Claude Conventions

## Pipeline Run Order

Run all seven stages end to end after activating the ETL venv:

```powershell
python etl/compounds/main.py --start 1 --end 7
# extract → normalize → dedupe → enrich → build_canonical → validate → export
```

`04_enrich` computes ADME inline and writes the final `smiles` / Lipinski / PAINS
columns directly into `compound_enrichment_results.csv`, so there are no separate
post-enrichment patch steps: `05_build_canonical` reads the enrichment output as-is.

## 04_enrich identity acceptance (source-first, corroboration-gated)

Compound identity is anchored on KNApSAcK's OWN published structure. Before any
external lookup, each candidate's member `c_id`s are matched against the
`knapsack_inchikey` / `knapsack_smiles` / `knapsack_formula` columns from the scraper
output (`knapsack/out/plants_compounds.csv`). When a published structure's formula
corroborates the raw representative formula (charge/desalt-aware via
`shared.identity.formula_matches`), that structure IS the identity:

- KNApSAcK source structure formula agrees → `knapsack_source_confirmed`
  (`evidence_type=knapsack+formula`, confidence 0.97). Structure fields are stored
  exactly as KNApSAcK publishes them; ADME is computed inline (see below); the
  PubChem/ChEMBL identity search is skipped entirely.

This is the primary accept path. When no member has a corroborating KNApSAcK
structure (the current on-disk state until the source-first re-scrape populates the
`knapsack_*` columns, so every candidate falls through here today), enrichment falls
back to the external PubChem/ChEMBL search, accepted only when corroborated:

- CAS synonym match AND formula agrees → `cas_formula_confirmed` (confidence 0.97)
- PubChem+ChEMBL agree on InChIKey AND formula agrees → `cross_source_confirmed` (0.97)
- strong name match AND formula agrees → `name_formula_confirmed` (0.90)

**Inline ADME (`properties.py`).** On the `knapsack_source_confirmed` path, ADME is
derived from the accepted SMILES/InChIKey via the sibling `04_enrich/properties.py`
module: RDKit for the Lipinski descriptors + molecular weight (`lipinski_source =
rdkit_computed`), one ChEMBL by-InChIKey lookup for `qed_score` / `num_ro5_violations`
(and `np_likeness_score` when ChEMBL has it, else the RDKit NP scorer), and RDKit
PAINS for `is_pains_positive`. This replaced the former post-hoc patch passes.

**Opportunistic disagreement flag.** If a PubChem/ChEMBL InChIKey for the compound is
ALREADY in the raw HTTP cache and disagrees with the accepted KNApSAcK InChIKey,
`knapsack_vs_external_disagreement` is appended to `match_reason`. This is cache-only
(no new fetch) and never overrides KNApSAcK's structure.

Everything else is REJECTED (structure fields left blank so 05 falls back to the raw
name_formula/name/cas identity, never a wrong InChIKey): `rejected_name_only`,
`rejected_formula_only`, `rejected_formula_mismatch`, `rejected_mw`,
`rejected_ambiguous_tie`, `rejected_uncorroborated` (all confidence 0.30, status
`review`). Salts/hydrates (`.`/`·` in the formula) never match a desalted formula.

`compound_enrichment_results.csv` now carries honest provenance for 05 to surface:
`match_strategy` (the values above), `evidence_type` (`knapsack+formula`, `cas+formula`,
`name+formula`, `cross_source+formula`, `name_only`, `formula_only`, `mw_only`,
`cas_no_formula_confirm`, `ambiguous`, `weak`, `none`), and an honest
`enrichment_confidence` (high only when structurally corroborated). It also carries the
inline-computed `lipinski_source` and `is_pains_positive` (formerly added by the patch
passes). `match_count` = distinct candidate structures; `match_rank` = the accepted
hit's rank (blank when rejected); for a `knapsack_source_confirmed` accept both are `1`.

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

## Inline ADME (`04_enrich/properties.py`)

Property derivation lives in the sibling `properties.py`, imported by `run.py`; it
replaced the former `patch_missing_smiles.py` / `patch_missing_lipinski.py` post-passes
(both removed). On a `knapsack_source_confirmed` accept:
- `rdkit_descriptors(smiles)` → `logp`, `hbond_donors`, `hbond_acceptors`, `tpsa`,
  `rotatable_bonds`, `molecular_weight` (`lipinski_source = rdkit_computed`).
- `chembl_detail_by_inchikey(inchi_key, cache_dir)` → `qed_score`, `num_ro5_violations`
  (and `np_likeness_score` when present), cache-first via the shared HTTP cache.
- `np_likeness(smiles)` (RDKit Contrib NP scorer) fills `np_likeness_score` when ChEMBL
  has none; `check_pains(smiles)` (RDKit PAINS catalog) sets `is_pains_positive`.

RDKit is installed in the ETL venv (`rdkit==2026.3.2`). No new dependencies.

## Key Files

| File | Purpose |
|------|---------|
| `04_enrich/run.py` | Main enrichment (KNApSAcK-source anchor + PubChem/ChEMBL fallback) |
| `04_enrich/properties.py` | Inline RDKit / ChEMBL / NP / PAINS property computation |
| `05_build_canonical/run.py` | Canonical ID assignment, alias table, plant-compound bridge |

## Do Not Touch

- `04_enrich/out/cache/http/` — raw API response cache; delete only to force re-fetch
- `04_enrich/out/cache/candidates/` — per-candidate enrichment cache; delete individual
  files to re-process specific candidates (or bump `ENRICH_LOGIC_VERSION` to recompute all)
- Any `out/` directory — written by pipeline scripts only
