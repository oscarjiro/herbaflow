# disease_targets ETL — AI Instructions

## Non-obvious conventions

**Input comes from `diseases/05_export/out/`** — do not change the `diseases_input` path in settings.yml without also confirming the upstream diseases pipeline has been re-run.

**Disease id resolution happens at fetch time and is xref-validated.** Open Targets uses EFO/MONDO IDs, not DOID. The fetch step runs the OT free-text search by disease name, then accepts a hit **only if its `dbXRefs` cross-reference the seed's curated ontology id** (`ontology_id` in `diseases.csv`, e.g. `DOID_3393` → CURIE `DOID:3393`, `mesh_D000544` → `MESH:D000544`). A disease with no cross-referenced hit is rejected to the review path (`diseases_unresolved` in the fetch manifest) rather than silently resolving to a wrong/narrower disease; a rejected disease then hard-fails `04_validate`'s `all_diseases_covered` check. The resolved id is cached in `01_fetch/cache/{disease_key}.json` (column name stays `efo_id`, though values may be MONDO ids — OT's `disease(efoId:)` arg accepts both). Delete cache files (or run with `--no-cache`) to force re-resolution. Ischemic Heart Disease (seed `DOID_3393`) resolves to `MONDO_0005010` "coronary artery disorder" (the concept carrying `DOID:3393`), not the narrower free-text top hit.

**`canonical_key` convention: `uniprot:{acc}` primary, `ensembl:{id}` fallback.** This is intentional — UniProt accessions are used for downstream overlap with compound targets (which come from ChEMBL). If a target has no SwissProt or TrEMBL entry in Open Targets, it falls back to Ensembl ID. Do not change this convention without updating compound_targets equivalents.

**UUID namespaces in `utils.py` are frozen.** `TARGET_NS`, `TARGET_ALIAS_NS`, and `DISEASE_TARGET_NS` produce all primary keys. Changing them invalidates every existing ID and breaks FK integrity in the database. Only change them if deliberately resetting all data.

**`out/` directories are pipeline-owned.** Never hand-edit CSV files under `out/`. Re-run the relevant step or steps to regenerate.

**`uniprot_source` values:** `uniprot_swissprot` = reviewed (preferred), `uniprot_trembl` = unreviewed (fallback). Both are acceptable — SwissProt is higher confidence.

**Score threshold applied twice:** once at fetch time as a GraphQL page-stop heuristic, once at normalize time as a hard filter. This ensures cached data fetched with a loose threshold is correctly filtered if settings change.

## Run order

```
01_fetch → 02_normalize → 03_build_canonical → 04_validate → 05_export
```

Each step reads from the previous step's `out/`. Use `main.py --start N --end N` to re-run individual steps.
