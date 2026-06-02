"""Ontology mapping step for the disease ETL pipeline.

Purpose
-------
Map curated disease names to controlled vocabularies such as Disease Ontology,
MeSH, or other configured sources. This step is deliberately conservative and
seed-driven: it prefers ontology values already present in the curated input,
then consults a local cache, and only performs optional online lookup when
explicitly enabled in settings.

Inputs
------
- settings.yml for pipeline configuration, preferred sources, cache settings,
  and optional online lookup controls
- The previous step output from diseases/01_normalize/out/ by default

Outputs
-------
- ontology mapping CSV in diseases/02_map_ontology/out/
- updated normalized/canonical-prep CSV in diseases/02_map_ontology/out/
- cache file updates when new mappings are found
- optional mapping report and run manifest in the same out/ directory

Behavior
--------
- Preserves raw and normalized source columns
- Prefers seed-provided ontology IDs and sources when available
- Uses a local cache first to avoid repeated lookups
- Falls back to optional online lookup only when enabled in settings
- Preserves provenance and source references
- Avoids aggressive inference and leaves rows unmapped when confidence is low
- Is idempotent and safe to rerun
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir, now_iso

from diseases.utils import (
    canonical_key,
    normalize_text,
    read_frame,
    clean_str,
    write_frame,
    SETTINGS_PATH,
)

SOURCE_NAME_TO_CODE = {
    "disease ontology": "doid",
    "mesh": "mesh",
    "mondo": "mondo",
    "omim": "omim",
}

KNOWN_ONTOLOGY_COLUMNS = (
    "ontology_id",
    "ontology_curie",
    "ontology_source",
    "ontology_label",
    "disease_ontology_id",
    "mesh_id",
    "mesh_ui",
    "doid_id",
    "mondo_id",
    "omim_id",
    "curie",
    "identifier",
)

OUTPUT_MAPPING_COLUMNS = [
    "disease_key",
    "disease_name_clean",
    "standardized_name",
    "ontology_id",
    "ontology_source",
    "ontology_description",
    "ontology_synonyms",
    "ontology_confidence",
    "ontology_status",
    "ontology_match_method",
    "ontology_query",
    "ontology_cache_hit",
]


def _resolve_path(base_dir: Path, raw_value: str, default_value: str) -> Path:
    """Resolve a configured path relative to the settings file directory."""
    path = Path(raw_value or default_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _resolve_paths(settings: dict[str, Any]) -> tuple[Path, Path, Path]:
    """Resolve input, output, and cache paths from settings."""
    paths = settings.get("paths", {})
    ontology_cfg = settings.get("ontology", {})

    normalize_out = _resolve_path(
        ETL_ROOT,
        str(paths.get("normalize_out", "diseases/01_normalize/out")),
        "diseases/01_normalize/out",
    )
    ontology_out = _resolve_path(
        ETL_ROOT,
        str(paths.get("ontology_out", "diseases/02_map_ontology/out")),
        "diseases/02_map_ontology/out",
    )

    cache_default = ontology_out / "ontology_cache.csv"
    cache_path = ontology_cfg.get("cache_path") or cache_default
    cache_path = _resolve_path(ETL_ROOT, str(cache_path), str(cache_default))

    return normalize_out, ontology_out, cache_path


def _resolve_input_path(normalize_out: Path) -> Path:
    """Resolve the normalized CSV to use as input for ontology mapping."""
    preferred = normalize_out / "disease_seed.csv"
    if preferred.exists():
        return preferred

    candidates = sorted(normalize_out.glob("*.csv"))
    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        raise FileNotFoundError(f"No CSV inputs found in {normalize_out}")

    raise FileNotFoundError(
        f"Could not resolve a single normalized CSV in {normalize_out}. "
        f"Expected disease_seed.csv or exactly one CSV file."
    )


def _pick_first_existing(columns: list[str], candidates: tuple[str, ...]) -> str | None:
    """Return the first column name that exists from a candidate list."""
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _infer_source_from_column_name(column_name: str) -> str | None:
    """Infer a human-readable ontology source name from a column name."""
    col = column_name.lower()

    if "mesh" in col:
        return "MeSH"
    if "doid" in col or "disease_ontology" in col:
        return "Disease Ontology"
    if "mondo" in col:
        return "MONDO"
    if "omim" in col:
        return "OMIM"
    return None


def _infer_source_from_curie(value: str) -> str | None:
    """Infer a source name from a CURIE-like identifier."""
    curie = clean_str(value)
    if not curie:
        return None

    prefix = curie.split(":", 1)[0].strip().upper()
    if prefix == "DOID":
        return "Disease Ontology"
    if prefix == "MESH":
        return "MeSH"
    if prefix == "MONDO":
        return "MONDO"
    if prefix == "OMIM":
        return "OMIM"
    return None


def _source_name_to_code(source_name: str | None) -> str | None:
    """Map a human-readable ontology source name to a search code."""
    if not source_name:
        return None
    return SOURCE_NAME_TO_CODE.get(source_name.strip().lower())


def _normalize_for_match(value: object) -> str:
    """Normalize text for conservative exact matching."""
    return normalize_text(value)


def _get_search_terms(row: pd.Series) -> list[str]:
    """Collect primary name and aliases into a prioritized list of search terms."""
    terms = []

    # 1. Primary Name (Highest Priority)
    primary = clean_str(row.get("disease_name_clean"))
    if primary:
        terms.append(primary)

    # 2. Aliases (Secondary Priority)
    aliases_raw = clean_str(row.get("synonym_clean"))
    if aliases_raw:
        # Split by semicolon and add unique terms not already in the list
        for alias in aliases_raw.split(";"):
            clean_alias = alias.strip()
            if clean_alias and clean_alias.lower() not in [t.lower() for t in terms]:
                terms.append(clean_alias)

    return terms


def _extract_seed_candidates(row: pd.Series) -> list[dict[str, str]]:
    """Extract any seed-provided ontology candidates from a normalized row."""
    candidates: list[dict[str, str]] = []
    columns = list(row.index)

    ontology_id = ""
    ontology_source = ""
    ontology_label = ""

    for col in columns:
        value = clean_str(row[col])
        if not value:
            continue

        col_l = col.lower()

        if col_l == "ontology_id":
            ontology_id = value
            continue
        if col_l == "ontology_curie":
            ontology_id = value
            if not ontology_source:
                ontology_source = _infer_source_from_curie(value) or ""
            continue
        if col_l == "ontology_source":
            ontology_source = value
            continue
        if col_l == "ontology_label":
            ontology_label = value
            continue

        if any(
            token in col_l
            for token in (
                "ontology",
                "disease_ontology",
                "mesh",
                "doid",
                "mondo",
                "omim",
                "curie",
            )
        ):
            source_guess = _infer_source_from_column_name(
                col_l
            ) or _infer_source_from_curie(value)
            if source_guess:
                candidates.append(
                    {
                        "ontology_id": value,
                        "ontology_source": source_guess,
                        "ontology_label": ontology_label,
                    }
                )

    if ontology_id:
        candidates.append(
            {
                "ontology_id": ontology_id,
                "ontology_source": ontology_source or "",
                "ontology_label": ontology_label,
            }
        )

    # Deduplicate exact repeats while preserving order.
    unique: list[dict[str, str]] = []
    seen: set[tuple[str, str, str]] = set()
    for candidate in candidates:
        key = (
            candidate.get("ontology_id", ""),
            candidate.get("ontology_source", ""),
            candidate.get("ontology_label", ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(candidate)

    return unique


def _preferred_source_order(preferred_sources: list[str]) -> list[str]:
    """Normalize preferred source names for ranking and comparisons."""
    ordered: list[str] = []
    seen: set[str] = set()
    for source in preferred_sources:
        cleaned = clean_str(source)
        if not cleaned:
            continue
        key = cleaned.strip().lower()
        if key in seen:
            continue
        seen.add(key)
        ordered.append(cleaned)
    return ordered


def _choose_seed_candidate(
    candidates: list[dict[str, str]],
    preferred_sources: list[str],
) -> tuple[dict[str, str] | None, bool]:
    """Choose the best seed-provided candidate and flag ambiguity when needed."""
    if not candidates:
        return None, False

    if len(candidates) == 1:
        return candidates[0], False

    preferred_map = {
        source.strip().lower(): idx for idx, source in enumerate(preferred_sources)
    }

    def rank(candidate: dict[str, str]) -> tuple[int, int]:
        source = candidate.get("ontology_source", "").strip().lower()
        if source in preferred_map:
            return (0, preferred_map[source])
        return (1, 999)

    ordered = sorted(candidates, key=rank)
    unique_ids = {
        (
            c.get("ontology_id", ""),
            c.get("ontology_source", ""),
            c.get("ontology_label", ""),
        )
        for c in candidates
        if c.get("ontology_id", "")
    }
    ambiguous = len(unique_ids) > 1
    return ordered[0], ambiguous


def _cache_key(row_key: str, query_key: str, source: str) -> tuple[str, str, str]:
    """Build a stable cache lookup key."""
    return row_key, query_key, source.strip().lower()


def _load_cache(cache_path: Path) -> pd.DataFrame:
    """Load the ontology cache or return an empty dataframe."""
    if not cache_path.exists():
        return pd.DataFrame(
            columns=[
                "disease_key",
                "query_key",
                "ontology_id",
                "ontology_source",
                "standardized_name",
                "ontology_description",
                "ontology_synonyms",
                "ontology_confidence",
                "ontology_match_method",
                "retrieved_at",
            ]
        )
    return read_frame(cache_path)


def _lookup_cache(
    cache_df: pd.DataFrame,
    disease_key: str,
    query_key: str,
    preferred_sources: list[str],
) -> dict[str, Any] | None:
    """Find a conservative cache match for the current disease row."""
    if cache_df.empty:
        return None

    required_cols = {"disease_key", "query_key", "ontology_id", "ontology_source"}
    if not required_cols.issubset(set(cache_df.columns)):
        return None

    candidates = cache_df[
        (cache_df["disease_key"].fillna("") == disease_key)
        | (cache_df["query_key"].fillna("") == query_key)
    ].copy()

    if candidates.empty:
        return None

    if preferred_sources:
        preferred_order = [s.strip().lower() for s in preferred_sources]
        candidates["_pref_rank"] = (
            candidates["ontology_source"]
            .fillna("")
            .str.strip()
            .str.lower()
            .map(
                lambda value: (
                    preferred_order.index(value) if value in preferred_order else 999
                )
            )
        )
        candidates = candidates.sort_values(by=["_pref_rank"], ascending=True)

    top = candidates.iloc[0].to_dict()
    top.pop("_pref_rank", None)
    return top


def _ols_search_exact(
    query: str,
    ontology_code: str | None,
    source_name: str,
    *,
    timeout: int = 10,
    max_results: int = 10,
) -> dict[str, Any] | None:
    """Perform a conservative exact-label lookup against OLS search results."""
    query_clean = clean_str(query)
    if not query_clean:
        return None

    params = {
        "q": query_clean,
        "type": "class",
        "rows": max_results,
    }
    if ontology_code:
        params["ontology"] = ontology_code

    url = "https://www.ebi.ac.uk/ols4/api/search?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "disease_etl/1.0",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except Exception:
        return None

    docs = payload.get("response", {}).get("docs", [])
    if not isinstance(docs, list) or not docs:
        return None

    query_norm = _normalize_for_match(query_clean)

    exact_hits: list[dict[str, Any]] = []
    for doc in docs:
        if not isinstance(doc, dict):
            continue
        label = clean_str(doc.get("label", ""))
        short_form = clean_str(doc.get("short_form", ""))
        if query_norm and query_norm == _normalize_for_match(label):
            exact_hits.append(doc)
        elif query_norm and query_norm == _normalize_for_match(short_form):
            exact_hits.append(doc)

    if not exact_hits:
        return None

    # Keep the first exact hit only to avoid over-mapping.
    doc = exact_hits[0]
    ontology_id = (
        clean_str(doc.get("short_form", ""))
        or clean_str(doc.get("obo_id", ""))
        or clean_str(doc.get("iri", ""))
    )
    ontology_label = clean_str(doc.get("label", ""))

    # Extract Description (OLS returns a list, we want a single string)
    desc_list = doc.get("description", [])
    description = ""
    for desc in desc_list:
        cleaned_desc = clean_str(desc)
        if any(x in cleaned_desc for x in ["[SN].", "Xref MGI."]):
            continue
        description = cleaned_desc
        break

    # Extract Synonyms
    synonyms = "; ".join(doc.get("exact_synonyms", []))

    if not ontology_id and not ontology_label:
        return None

    return {
        "ontology_id": ontology_id,
        "ontology_source": source_name,
        "standardized_name": ontology_label,
        "ontology_description": description,
        "ontology_synonyms": synonyms,
        "ontology_confidence": 0.90,
        "ontology_status": "matched",
        "ontology_match_method": "online_exact",
        "ontology_query": query_clean,
        "ontology_cache_hit": "no",
    }


def _online_lookup(
    query: str,
    preferred_sources: list[str],
    *,
    timeout: int = 10,
    max_results: int = 10,
) -> dict[str, Any] | None:
    """Attempt optional online lookup using preferred sources only."""
    if not query:
        return None

    sources = preferred_sources or []
    for source_name in sources:
        source_code = _source_name_to_code(source_name)
        if not source_code:
            continue
        hit = _ols_search_exact(
            query, source_code, source_name, timeout=timeout, max_results=max_results
        )
        if hit is not None:
            return hit

    return None


def _mapping_from_seed_candidate(
    candidate: dict[str, str],
    query: str,
    ambiguous: bool,
) -> dict[str, Any]:
    """Convert a seed-provided ontology candidate into a mapping record."""
    confidence = 0.85 if ambiguous else 1.00
    status = "ambiguous" if ambiguous else "matched"
    return {
        "ontology_id": clean_str(candidate.get("ontology_id", "")),
        "ontology_source": clean_str(candidate.get("ontology_source", "")),
        "standardized_name": clean_str(candidate.get("standardized_name", "")),
        "ontology_confidence": confidence,
        "ontology_status": status,
        "ontology_match_method": "seed_provided",
        "ontology_query": query,
        "ontology_cache_hit": "no",
        "ontology_description": "",
        "ontology_synonyms": "",
    }


def _empty_mapping(query: str) -> dict[str, Any]:
    """Create an unmapped record."""
    return {
        "ontology_id": "",
        "ontology_source": "",
        "ontology_confidence": 0.0,
        "ontology_status": "unmapped",
        "ontology_match_method": "none",
        "ontology_query": query,
        "ontology_cache_hit": "no",
        "ontology_description": "",
        "ontology_synonyms": "",
    }


def _build_cache_row(
    disease_key: str, query_key: str, mapping: dict[str, Any]
) -> dict[str, Any]:
    """Build a cache row from a resolved mapping."""
    return {
        "disease_key": disease_key,
        "query_key": query_key,
        "ontology_id": clean_str(mapping.get("ontology_id", "")),
        "ontology_source": clean_str(mapping.get("ontology_source", "")),
        "standardized_name": clean_str(mapping.get("standardized_name", "")),
        "ontology_description": clean_str(mapping.get("ontology_description", "")),
        "ontology_synonyms": clean_str(mapping.get("ontology_synonyms", "")),
        "ontology_confidence": float(mapping.get("ontology_confidence", 0.0) or 0.0),
        "ontology_match_method": clean_str(mapping.get("ontology_match_method", "")),
        "retrieved_at": now_iso(),
    }


def _update_cache(
    cache_df: pd.DataFrame, new_rows: list[dict[str, Any]]
) -> pd.DataFrame:
    """Append new mappings to the cache and deduplicate conservatively."""
    if not new_rows:
        return cache_df

    new_df = pd.DataFrame(new_rows)
    if cache_df.empty:
        combined = new_df.copy()
    else:
        combined = pd.concat([cache_df, new_df], ignore_index=True)

    for col in ("disease_key", "query_key", "ontology_id", "ontology_source"):
        if col not in combined.columns:
            combined[col] = ""

    # Keep the newest entry for duplicate keys.
    combined = combined.drop_duplicates(
        subset=["disease_key", "query_key", "ontology_id", "ontology_source"],
        keep="last",
    )
    return combined


def run(settings_path: str | Path = SETTINGS_PATH) -> dict[str, Any]:
    """Run the ontology mapping step and return a compact summary."""
    settings_path = Path(settings_path)
    settings = load_settings("diseases")
    logger = shared_setup_logging("diseases.02_map_ontology", settings)

    ontology_cfg = settings.get("ontology", {})
    preferred_sources = _preferred_source_order(
        list(ontology_cfg.get("preferred_sources", []))
    )
    mapping_enabled = bool(ontology_cfg.get("enable_mapping", True))
    online_lookup_enabled = bool(ontology_cfg.get("online_lookup", True))
    ols_timeout = int(ontology_cfg.get("request_timeout", 10))
    ols_max_results = int(ontology_cfg.get("max_results", 10))

    normalize_out, ontology_out, cache_path = _resolve_paths(settings)
    ensure_dir(ontology_out)
    ensure_dir(cache_path.parent)

    input_path = _resolve_input_path(normalize_out)
    df = read_frame(input_path)
    df_out = df.copy()

    if "disease_name_clean" not in df_out.columns:
        df_out["disease_name_clean"] = df_out.get(
            "disease_name", df_out.get("name", df_out.get("disease", ""))
        )
        df_out["disease_name_clean"] = df_out["disease_name_clean"].map(clean_str)

    if "disease_key" not in df_out.columns:
        df_out["disease_key"] = df_out["disease_name_clean"].map(canonical_key)

    cache_df = _load_cache(cache_path)
    cache_updates: list[dict[str, Any]] = []
    mapping_rows: list[dict[str, Any]] = []

    matched_count = 0
    unmatched_count = 0
    ambiguous_count = 0

    for _, row in df_out.iterrows():
        # 1. Harvest all possible search terms (Primary Name + Aliases)
        search_terms = _get_search_terms(row)
        primary_query = search_terms[0] if search_terms else ""
        disease_key = clean_str(row.get("disease_key", "")) or canonical_key(
            primary_query
        )

        mapping: dict[str, Any] | None = None
        cache_hit = False
        ambiguous = False
        final_query_used = primary_query  # Track which specific alias actually worked

        # TIER 1: SEED CANDIDATES (Manual Overrides)
        # We check this before the loop because manual IDs always win.
        seed_candidates = _extract_seed_candidates(row)
        if mapping_enabled and seed_candidates:
            chosen, ambiguous = _choose_seed_candidate(
                seed_candidates, preferred_sources
            )
            if chosen is not None:
                mapping = _mapping_from_seed_candidate(chosen, primary_query, ambiguous)
                final_query_used = primary_query

        # TIER 2 & 3: MULTI-TERM FAILOVER (Cache then Online)
        if mapping is None:
            for term in search_terms:
                query_key = canonical_key(term)

                # A. Check Local Cache for this specific term/alias
                cached = _lookup_cache(
                    cache_df, disease_key, query_key, preferred_sources
                )
                if cached is not None:
                    mapping = {
                        "ontology_id": clean_str(cached.get("ontology_id", "")),
                        "ontology_source": clean_str(cached.get("ontology_source", "")),
                        "standardized_name": clean_str(
                            cached.get("standardized_name", "")
                        ),
                        "ontology_description": clean_str(
                            cached.get("ontology_description", "")
                        ),
                        "ontology_synonyms": clean_str(
                            cached.get("ontology_synonyms", "")
                        ),
                        "ontology_confidence": float(
                            cached.get("ontology_confidence", 0.0) or 0.0
                        ),
                        "ontology_status": "matched",
                        "ontology_match_method": "cache",
                        "ontology_query": term,
                        "ontology_cache_hit": "yes",
                    }
                    cache_hit = True
                    final_query_used = term
                    break  # Success! Stop searching through aliases.

                # B. Online Lookup for this specific term/alias
                if mapping_enabled and online_lookup_enabled:
                    online = _online_lookup(
                        term,
                        preferred_sources,
                        timeout=ols_timeout,
                        max_results=ols_max_results,
                    )
                    if online is not None:
                        mapping = online
                        final_query_used = term
                        break  # Success! Stop searching through aliases.

        if mapping is None:
            mapping = _empty_mapping(primary_query)

        # Update cache hit flag based on final result
        if cache_hit:
            mapping["ontology_cache_hit"] = "yes"

        # Update global counters
        if mapping["ontology_status"] in {"matched", "ambiguous"} and clean_str(
            mapping.get("ontology_id", "")
        ):
            matched_count += 1
            if mapping["ontology_status"] == "ambiguous":
                ambiguous_count += 1
        else:
            unmatched_count += 1

        # Build the final mapping record for this row
        mapping_result = {
            "disease_key": disease_key,
            "disease_name_clean": clean_str(row.get("disease_name_clean", "")),
            "ontology_id": clean_str(mapping.get("ontology_id", "")),
            "ontology_source": clean_str(mapping.get("ontology_source", "")),
            "ontology_confidence": float(
                mapping.get("ontology_confidence", 0.0) or 0.0
            ),
            "standardized_name": clean_str(
                mapping.get("standardized_name", "")
            ),  # alias for label
            "ontology_description": clean_str(mapping.get("ontology_description", "")),
            "ontology_synonyms": clean_str(mapping.get("ontology_synonyms", "")),
            "ontology_status": clean_str(mapping.get("ontology_status", "")),
            "ontology_match_method": clean_str(mapping.get("ontology_match_method", "")),
            "ontology_query": final_query_used,
            "ontology_cache_hit": clean_str(mapping.get("ontology_cache_hit", "no")),
        }
        mapping_rows.append(mapping_result)

        # Sync the mapping results back into the main DataFrame (df_out)
        current_index = len(mapping_rows) - 1
        for key in OUTPUT_MAPPING_COLUMNS:
            # Ensure the column exists in the DataFrame
            if key not in df_out.columns:
                df_out[key] = ""

            value = mapping_result.get(key, "")
            df_out.at[df_out.index[current_index], key] = (
                str(value) if value is not None else ""
            )

        # Queue successful new matches for the cache update
        if mapping["ontology_status"] in {"matched", "ambiguous"} and clean_str(
            mapping.get("ontology_id", "")
        ):
            # We cache based on the canonical key of the term that actually worked
            working_query_key = canonical_key(final_query_used)
            cache_updates.append(
                _build_cache_row(disease_key, working_query_key, mapping)
            )

    # Ensure the output dataframe contains the mapping fields in a stable order.
    for col in OUTPUT_MAPPING_COLUMNS:
        if col not in df_out.columns:
            df_out[col] = ""

    ordered_columns = list(df.columns)
    for col in ("disease_name_clean", "disease_key"):
        if col in df_out.columns and col not in ordered_columns:
            ordered_columns.append(col)
    for col in OUTPUT_MAPPING_COLUMNS:
        if col not in ordered_columns:
            ordered_columns.append(col)

    df_out = df_out[ordered_columns]

    normalized_out_path = ontology_out / input_path.name
    write_frame(df_out, normalized_out_path)

    mapping_df = pd.DataFrame(mapping_rows)
    mapping_path = ontology_out / "ontology_mapping.csv"
    write_frame(mapping_df, mapping_path)

    report_path = ontology_out / "mapping_report.csv"
    write_frame(mapping_df, report_path)

    # Generate the flattened search map (Alias -> Disease Key)
    # This is what your App will use for the search bar!
    alias_map_rows = []
    for _, row in df_out.iterrows():
        d_key = row["disease_key"]

        # 1. Add Primary Name
        alias_map_rows.append(
            {
                "alias": row["disease_name_clean"],
                "disease_key": d_key,
                "type": "primary",
            }
        )

        # 2. Add User-provided Aliases
        if clean_str(row.get("synonym_clean")):
            for s in str(row["synonym_clean"]).split(";"):
                if s.strip():
                    alias_map_rows.append(
                        {
                            "alias": s.strip().lower(),
                            "disease_key": d_key,
                            "type": "user_alias",
                        }
                    )

        # 3. Add Ontology-provided medical synonyms (the new "gold")
        if clean_str(row.get("ontology_synonyms")):
            for s in str(row["ontology_synonyms"]).split(";"):
                if s.strip():
                    alias_map_rows.append(
                        {
                            "alias": s.strip().lower(),
                            "disease_key": d_key,
                            "type": "ontology_synonym",
                        }
                    )

    write_frame(pd.DataFrame(alias_map_rows), ontology_out / "disease_alias_map.csv")

    report_json = {
        "module_name": settings.get("module_name", "disease_etl"),
        "step": "02_map_ontology",
        "batch_id": settings.get("batch_id", ""),
        "input_path": str(input_path),
        "output_path": str(normalized_out_path),
        "mapping_path": str(mapping_path),
        "cache_path": str(cache_path),
        "row_count": int(len(df_out)),
        "matched_count": int(matched_count),
        "unmatched_count": int(unmatched_count),
        "ambiguous_count": int(ambiguous_count),
        "preferred_sources": preferred_sources,
        "online_lookup_enabled": online_lookup_enabled,
        "timestamp": now_iso(),
    }

    manifest_path = ontology_out / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(report_json, f, indent=2, ensure_ascii=False)
        f.write("\n")

    if cache_updates:
        cache_df = _update_cache(cache_df, cache_updates)
        write_frame(cache_df, cache_path)

    log_path = ontology_out / "run.log"
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"Ontology mapping completed at {report_json['timestamp']}\n")
        f.write(f"Input: {input_path}\n")
        f.write(f"Output: {normalized_out_path}\n")
        f.write(f"Mapping CSV: {mapping_path}\n")
        f.write(f"Cache: {cache_path}\n")
        f.write(f"Matched: {matched_count}\n")
        f.write(f"Unmatched: {unmatched_count}\n")
        f.write(f"Ambiguous: {ambiguous_count}\n")

    logger.info(
        "Ontology mapping complete: %s rows (%s matched, %s unmatched, %s ambiguous)",
        len(df_out),
        matched_count,
        unmatched_count,
        ambiguous_count,
    )
    return report_json


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Map curated disease names to controlled vocabularies with cache-first behavior."
    )
    parser.add_argument(
        "--settings",
        default=SETTINGS_PATH,
        help="Path to the pipeline settings.yml file (default: settings.yml)",
    )
    args = parser.parse_args()
    run(args.settings)


if __name__ == "__main__":
    main()
