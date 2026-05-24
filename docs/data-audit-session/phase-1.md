# Phase 1: Plant Data Quality

> Audit date: 2026-05-24
> Sequential tasks: P1-A → P1-B → P1-C → P1-D

---

## P1-A: Duplicate Plant Root Cause

### Scope

From Phase 0: 19 species × 2 rows = 38 affected plants.

### ETL Pipeline Trace

```
knapsack/main.py            →  etl/knapsack/out/plants.csv
plants/01_extract/run.py    →  plants/01_extract/out/stg_plants.csv
plants/02_normalize_taxonomy/run.py  →  plants/02_normalize_taxonomy/out/normalized_plants.csv
plants/03_match_gbif/run.py →  plants/03_match_gbif/out/gbif_matches.csv
plants/04_build_canonical/run_part1.py  →  accepted_plants.csv
plants/04_build_canonical/run_part2.py  →  plants/04_build_canonical/out/plants.csv  (DB seed)
```

The scraper deduplicates by `detail_url` (the KNApSAcK organism search URL). Each KNApSAcK organism URL is unique to a scraped name string, so different synonym spellings for the same species each produce a distinct row. The normalize step performs no cross-row deduplication — it only normalizes whitespace and splits authorship. The GBIF match step (`build_lookup_table`) deduplicates by `canonical_lookup_key` (lowercased, punctuation-stripped name), so it will collapse e.g. "Curcuma longa" and "Curcuma longa L." into one query — but it does NOT collapse botanically synonymous names like "Curcuma domestica" and "Curcuma soloensis" that are spelled differently from "Curcuma longa".

The `build_seed_files` function in run_part2.py groups rows by `__canonical_key_preview`, which is derived from `canonical_scientific_name_from_row()` — the GBIF-returned `accepted_name`. Two rows that both have `accepted_name = "Curcuma longa L."` should collapse into the same group. However, the grouping key also includes `authorship`, and the `build_canonical_key()` function appends the authorship when present:

```python
def build_canonical_key(canonical_scientific_name: str, authorship: str) -> str:
    name_key = fold_key_text(canonical_scientific_name)
    author_key = fold_key_text(authorship)
    if author_key:
        return f"{name_key}|{author_key}"
    return name_key
```

Two GBIF synonyms for the same accepted species can return different `authorship` values. When one synonym row carries `authorship = "L."` (the author of *Curcuma longa*) and another carries `authorship = "Valeton"` (the author of the synonym *Curcuma soloensis*), their canonical keys become `"curcuma longa l|l"` vs `"curcuma longa l|valeton"` — distinct groups — and each produces a separate DB row with a different `gbif_usage_key` (the synonym's own usage key, not the accepted species key).

### Root Cause

**File:** `etl/plants/04_build_canonical/run_part2.py`, function `canonicalize_group`

**The bug is two-fold:**

1. **Wrong key for plant_id:** `gbif_usage_key` used to generate `plant_id` is taken from the GBIF response's `usage.key` field — the synonym's own key — not from `gbif_accepted_usage_key`. This means "Curcuma soloensis" (a synonym, usage key 2757626) generates a different plant_id than "Curcuma longa" (accepted, usage key 2757624), even though GBIF says they are the same species.

2. **Authorship bleeds into the grouping key:** `build_canonical_key()` appends authorship to the canonical key. The authorship stored in each row is the author of the matched (synonym) name, not the author of the accepted name. Two synonym rows that both resolve to the same accepted species can carry different authorships, producing different `__canonical_key_preview` values and preventing grouping.

The combination means: KNApSAcK "Curcuma domestica Valeton" → GBIF synonym match → `gbif_usage_key=2757628`, `authorship="Valeton"` → canonical key `"curcuma longa l|valeton"` → `plant_id = stable_id(PLANT_NS, "2757628")` = `pl_bf36045f554639d9e1a91fda`.

Separately, KNApSAcK "Curcuma longa" → GBIF accepted match → `gbif_usage_key=2757624`, `authorship="L."` → canonical key `"curcuma longa l|l"` → `plant_id = stable_id(PLANT_NS, "2757624")` = `pl_b0133f9d541a67e77134345d`.

Two DB rows for the same biological species.

### Code Evidence

**`etl/plants/utils.py` — plant_id uses gbif_usage_key verbatim:**
```python
def plant_id(gbif_usage_key: str | int) -> str:
    """Return a deterministic UUID v5 for the given GBIF usage key."""
    return stable_id(PLANT_NS, str(gbif_usage_key))
```

**`etl/plants/04_build_canonical/run_part2.py` — gbif_key selection (line 388):**
```python
gbif_key = (
    normalize_id_like(rep.get("gbif_usage_key", ""))
    or normalize_id_like(rep.get("gbif_accepted_usage_key", ""))
    or canonical_key
)
plant_id = build_plant_id(gbif_key)
```
`gbif_usage_key` is preferred over `gbif_accepted_usage_key`. For a synonym row, `gbif_usage_key` is the synonym's own key, which differs from the accepted species key.

**`etl/plants/04_build_canonical/run_part2.py` — canonical key includes authorship (lines 320–325):**
```python
def build_canonical_key(canonical_scientific_name: str, authorship: str) -> str:
    name_key = fold_key_text(canonical_scientific_name)
    author_key = fold_key_text(authorship)
    if author_key:
        return f"{name_key}|{author_key}"
    return name_key
```
The authorship embedded here is the synonym author, not the accepted name author.

**Confirmed from intermediate outputs — `gbif_matches.csv` rows for all three Curcuma longa synonyms:**
```
# Curcuma domestica Valeton → synonym of Curcuma longa L.
input_name=Curcuma domestica, gbif_usage_key=2757628, gbif_accepted_usage_key=2757624, taxonomic_status=SYNONYM

# Curcuma longa → accepted species
input_name=Curcuma longa, gbif_usage_key=2757624, gbif_accepted_usage_key=2757624, taxonomic_status=ACCEPTED

# Curcuma soloensis Valeton → synonym of Curcuma longa L.
input_name=Curcuma soloensis, gbif_usage_key=2757626, gbif_accepted_usage_key=2757624, taxonomic_status=SYNONYM
```

**Note:** Curcuma domestica (usage key 2757628) was correctly merged into the Curcuma soloensis group (the `build_canonical_part2_report.txt` confirms: `"Curcuma domestica → merged into representative: Curcuma longa L. | raw_plant_id=159"`). Only Curcuma soloensis (usage key 2757626, authorship "Valeton") and Curcuma longa (usage key 2757624, authorship "L.") produced separate plant rows.

**Final plants.csv confirms two rows:**
```
pl_b0133f9d541a67e77134345d, canonical_key=curcuma longa l|l,    gbif_usage_key=2757624, ACCEPTED
pl_bf36045f554639d9e1a91fda, canonical_key=curcuma longa l|valeton, gbif_usage_key=2757626, SYNONYM
```

### Hypothesis Verdict

The original hypothesis was partially correct but missed a key detail.

**What was right:** Different synonym spellings in KNApSAcK do result in different GBIF `usageKey` values for synonym rows, and those different keys drive different UUIDs.

**What was wrong / more nuanced:** The dedup failure is NOT in the knapsack scraper (which correctly deduplicates by `detail_url`). It is NOT in the GBIF match step (which correctly returns `gbif_accepted_usage_key = 2757624` for both rows). The failure is in **run_part2.py's grouping logic**, which uses `gbif_usage_key` (synonym key) instead of `gbif_accepted_usage_key` for both the canonical key and the plant_id — AND embeds the synonym's authorship into the grouping key, preventing rows that share the same accepted species from being merged.

The alternative hypothesis (GBIF fallback key) was not the cause. GBIF matched all variants successfully.

### Fix Required

P1-B must fix two things in `etl/plants/04_build_canonical/run_part2.py`:

1. **Use `gbif_accepted_usage_key` as the plant_id seed.** Change the `gbif_key` selection in `canonicalize_group` to prefer `gbif_accepted_usage_key` over `gbif_usage_key`:
   ```python
   gbif_key = (
       normalize_id_like(rep.get("gbif_accepted_usage_key", ""))
       or normalize_id_like(rep.get("gbif_usage_key", ""))
       or canonical_key
   )
   ```

2. **Strip authorship from the grouping key.** The `__canonical_key_preview` used to group rows before `canonicalize_group` is called should be based only on the accepted species name (without authorship), so that all synonym rows for the same accepted species land in the same group. Change `build_canonical_key` usage in the grouping step to pass an empty authorship, or introduce a separate grouping key function that ignores authorship.

After the fix, all KNApSAcK entries that GBIF resolves to the same `gbif_accepted_usage_key` will collapse to a single plant row with a single `plant_id`. The existing synonym names will be preserved as `alias_type=synonym_variant` rows in `plant_aliases`.

The 19 × 2 = 38 affected DB rows should reduce to 19 after re-running the pipeline and reloading. The compound associations currently split across two plant_ids will also need to be re-mapped to the single surviving plant_id (this is a downstream concern for the load step).

---

## P1-B: Fix Applied

> Applied: 2026-05-24

### What Was Changed

**File:** `etl/plants/04_build_canonical/run_part2.py` only. `run_part1.py` has no grouping logic — no changes needed there.

---

#### Fix 1 — Prefer `gbif_accepted_usage_key` for plant_id generation

**Function:** `canonicalize_group` (line 388)

**Before:**
```python
gbif_key = normalize_id_like(rep.get("gbif_usage_key", "")) or normalize_id_like(rep.get("gbif_accepted_usage_key", "")) or canonical_key
```

**After:**
```python
gbif_key = (
    normalize_id_like(rep.get("gbif_accepted_usage_key", ""))
    or normalize_id_like(rep.get("gbif_usage_key", ""))
    or canonical_key
)
```

**Rationale:** For synonym rows, `gbif_usage_key` is the synonym's own GBIF key (e.g. 2757626 for *Curcuma soloensis*), which differs from the accepted species key (2757624 for *Curcuma longa*). Using the synonym key as the plant_id seed produced a different UUID than the accepted-species row. Preferring `gbif_accepted_usage_key` ensures all synonyms and the accepted name converge on the same `plant_id`.

---

#### Fix 2 — Strip authorship from the grouping key

**Location:** `build_seed_files` function, `__canonical_key_preview` computation (lines 553–563)

**Before:**
```python
work["__canonical_key_preview"] = work.apply(
    lambda r: build_canonical_key(
        canonical_scientific_name_from_row(r),
        authorship_from_row(r),
    ),
    axis=1,
)
```

**After:**
```python
# Use accepted name WITHOUT authorship for grouping so that all synonym rows
# that GBIF resolves to the same accepted species land in the same group.
# Authorship is preserved in the output canonical_key via canonicalize_group().
work["__canonical_key_preview"] = work.apply(
    lambda r: build_canonical_key(
        canonical_scientific_name_from_row(r),
        "",
    ),
    axis=1,
)
```

**Rationale:** `authorship_from_row` returns the author of the *matched* (synonym) name — e.g. `"Valeton"` for *Curcuma soloensis*. Two synonym rows that resolve to the same accepted species can carry different authorships, making their `__canonical_key_preview` values distinct and preventing grouping. Passing `""` as authorship ensures the grouping key is based solely on the accepted species name, so all variants collapse into one group. The full `canonical_key` (with authorship from the representative row) is still computed inside `canonicalize_group()` and written to the output.

---

### Impact

- All 19 duplicate species pairs (38 DB rows) will collapse to 19 single rows after ETL re-run.
- `plant_id` for each species will be derived from `gbif_accepted_usage_key`, making it stable regardless of whether the KNApSAcK input spelled the accepted name or a synonym.
- Synonym names are preserved as `alias_type=synonym_variant` entries in `plant_aliases.csv`.
- ETL re-run is deferred — code-only fix.
