# disease_targets ETL — AI Instructions

## Non-obvious conventions

**Input comes from `diseases/05_export/out/`** — do not change the `diseases_input` path in settings.yml without also confirming the upstream diseases pipeline has been re-run.

**EFO ID resolution happens at fetch time.** Open Targets uses EFO/MONDO IDs, not DOID. The fetch step resolves disease names to EFO IDs via the OT search API and caches the result in `01_fetch/cache/{disease_key}.json`. Delete cache files to force re-resolution.

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
