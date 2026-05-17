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

Note: `qed_score` and `np_likeness_score` are only populated from ChEMBL (Pass 1).
RDKit pass leaves them blank. Compounds with neither a `chembl_id` nor a usable
`smiles` remain unresolved.

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
