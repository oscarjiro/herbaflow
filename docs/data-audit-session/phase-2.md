# Phase 2: Compound Data Quality

> Audit date: 2026-05-24
> Tasks P2-A and P2-B run in parallel; P2-C sequential after both complete.

---

## P2-A: Compound Name Canonicality

<!-- TO BE FILLED BY P2-A SUBAGENT -->

---

## P2-B: ADME Coverage Assessment

### Null Rate Findings (Phase 0 baseline)

ADME coverage by `lipinski_source`:

| lipinski_source | total | has_qed | has_np_likeness_score |
|---|---|---|---|
| rdkit_computed | 5,962 | 0 | 0 |
| null (ChEMBL) | 5,343 | 5,335 | 5,335 |

Overall null rate for `np_likeness_score`: **5,962 / 11,305 = 52.7%**

### Threshold Check

The data quality threshold for null rates is **20%**. The `np_likeness_score` null rate of
52.7% far exceeds this threshold. This is critical because Stage 2 ADME uses an NP exception
pathway: compounds with high NP-likeness score can pass even if they violate Lipinski rules.
With 52.7% of compounds carrying no NP score, this exception pathway is blind for the majority
of the compound set — all 5,962 `rdkit_computed` compounds could not benefit from the NP
exception regardless of their actual natural-product character.

### Root Cause

The `rdkit_computed` group (5,962 compounds) has zero `np_likeness_score` values because
`patch_missing_lipinski.py` Pass 2 (RDKit) explicitly left `np_likeness_score` blank with
the comment `# qed_score and np_likeness_score require additional modules; leave blank`.
The RDKit NP scorer is available via RDKit Contrib (`NP_Score/npscorer.py`) but was not
wired up.

### Fix Applied

File modified: `etl/compounds/04_enrich/patch_missing_lipinski.py`

Changes:
1. Added `_load_np_scorer()` helper — loads RDKit Contrib NP scorer once at startup, returns
   `(None, None)` gracefully if unavailable.
2. Added `compute_np_score(smiles, npscorer_mod, fscore)` helper — computes score for one
   SMILES, returns empty string on any failure.
3. Added **Pass 2b** in `main()` — after the existing RDKit Lipinski pass, iterates all
   result rows where `np_likeness_score` is null but `smiles` is present, applies NP score
   via RDKit NP scorer.
4. Updated `lipinski_source` to append `+rdkit_np` suffix when NP score is added via RDKit
   (e.g. `rdkit_computed+rdkit_np`, `chembl_api+rdkit_np`).
5. Pass 2b is guarded by the same `--no-rdkit` flag as Pass 2.
6. Write condition updated to flush CSV when only NP scores changed (no Lipinski changes).
7. Module docstring and summary log updated.

### lipinski_source Values Post-Patch

| lipinski_source | meaning |
|---|---|
| `chembl_api` | All ADME + NP from ChEMBL |
| `chembl_api+rdkit_np` | ADME from ChEMBL; NP score added by RDKit (ChEMBL returned empty) |
| `rdkit_computed` | Lipinski from RDKit; NP scorer unavailable at runtime |
| `rdkit_computed+rdkit_np` | Lipinski + NP-likeness both from RDKit |
| `rdkit_np` | NP-likeness only added (Lipinski already present from a prior source) |
| `` (empty) | Compound unresolved — no chembl_id and no usable SMILES |

### Limitations

- **NP scorer availability is a runtime concern.** The code degrades gracefully with a
  warning if `NP_Score/npscorer.py` is not found in RDKit Contrib. The ETL venv has
  `rdkit==2026.3.2`; NP_Score has been bundled in RDKit Contrib since RDKit 2009 and is
  expected to be present.
- **`qed_score` is not computed by RDKit.** The `rdkit_computed` group will continue to
  have null `qed_score`. This is a separate issue and not in scope for P2-B.
- Pass 2b also covers any ChEMBL-sourced compounds where ChEMBL returned an empty
  `np_likeness_score`, reducing the overall null rate beyond the `rdkit_computed` cohort.

### Adjacent Findings

- `qed_score` null rate for `rdkit_computed` group is also 100% (5,962 / 11,305 = 52.7%).
  Computing QED via RDKit (`rdkit.Chem.QED.qed()`) would close this gap similarly. Not
  fixed here (out of scope for P2-B; recommend as a follow-up task).

---

## P2-C: Alias Completeness

<!-- TO BE FILLED BY P2-C SUBAGENT -->
