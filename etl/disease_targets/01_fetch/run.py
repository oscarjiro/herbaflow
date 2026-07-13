"""
01_fetch/run.py — Fetch disease-target associations from Open Targets Platform.

For each canonical disease:
  1. Resolve the Open Targets disease id via OT search, then accept the hit only
     if its dbXRefs cross-reference the seed's curated ontology id (DOID/MeSH).
     A disease with no cross-referenced hit is rejected to the review path.
  2. Paginate associatedTargets query
  3. Cache raw JSON per disease
  4. Write flat raw_associations.csv
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from disease_targets.utils import clean_str, make_slug_key, read_frame, write_frame
from shared.utils import (
    ETL_ROOT,
    ensure_dir,
    load_settings,
    make_run_id,
    now_iso,
    setup_logging,
    write_json,
)

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

# `dbXRefs` is a documented field on the Open Targets GraphQL `Disease` type
# (`dbXRefs: [String!]!`, cross-references to external disease ontologies). Its
# entries are CURIEs such as "DOID:3393" or "MESH:D000544" (uppercase prefix,
# colon-delimited) — verified live against the OT API v4 schema. We pull it inline
# on each search hit via an inline fragment on the Disease object so we can confirm
# the top free-text match actually corresponds to the seed's curated ontology id.
SEARCH_QUERY = """
query SearchDisease($queryString: String!) {
  search(queryString: $queryString, entityNames: ["disease"], page: {index: 0, size: 10}) {
    hits {
      id
      name
      entity
      object {
        ... on Disease {
          dbXRefs
        }
      }
    }
  }
}
"""

ASSOCIATIONS_QUERY = """
query DiseaseTargets($efoId: String!, $index: Int!, $size: Int!) {
  disease(efoId: $efoId) {
    id
    name
    associatedTargets(page: {index: $index, size: $size}) {
      count
      rows {
        score
        target {
          id
          approvedSymbol
          approvedName
          proteinIds {
            id
            source
          }
        }
      }
    }
  }
}
"""

# ---------------------------------------------------------------------------
# API helpers
# ---------------------------------------------------------------------------


def _gql(endpoint: str, query: str, variables: dict, cfg: dict, log) -> dict | None:
    timeout = cfg["api"]["timeout_seconds"]
    attempts = cfg["api"]["retry_attempts"]
    delay = cfg["api"]["retry_delay_seconds"]

    for attempt in range(1, attempts + 1):
        try:
            resp = requests.post(
                endpoint,
                json={"query": query, "variables": variables},
                timeout=timeout,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            data = resp.json()
            if "errors" in data:
                log.warning("GraphQL errors: %s", data["errors"])
                return None
            return data.get("data")
        except Exception as exc:
            log.warning("Attempt %d/%d failed: %s", attempt, attempts, exc)
            if attempt < attempts:
                time.sleep(delay * attempt)
    return None


def ontology_curie(ontology_id: str | None) -> str:
    """Convert a seed ontology id to an Open Targets dbXRefs CURIE.

    The `diseases.csv` seed carries ids like ``DOID_3393`` or ``mesh_D000544``;
    Open Targets `dbXRefs` uses the CURIE form ``DOID:3393`` / ``MESH:D000544``
    (uppercase prefix, colon-delimited). Returns "" if there is no usable id.
    """
    raw = clean_str(ontology_id)
    if not raw or "_" not in raw:
        return ""
    prefix, _, local = raw.partition("_")
    if not prefix or not local:
        return ""
    return f"{prefix.upper()}:{local}"


def select_xref_hit(hits: list[dict], expected_curie: str) -> dict | None:
    """Return the first search hit whose `dbXRefs` contains ``expected_curie``.

    Matching is case-insensitive on the full CURIE. Returns None if no hit
    cross-references the seed's curated ontology id — the caller then rejects
    the disease to the review/error path rather than trusting the top hit.
    """
    if not expected_curie:
        return None
    wanted = expected_curie.upper()
    for hit in hits:
        obj = hit.get("object") or {}
        xrefs = {str(x).upper() for x in (obj.get("dbXRefs") or [])}
        if wanted in xrefs:
            return hit
    return None


def resolve_disease_id(
    disease_name: str, ontology_id: str | None, endpoint: str, cfg: dict, log
) -> tuple[str | None, str]:
    """Resolve a seed disease to an Open Targets disease id, xref-validated.

    Runs the free-text OT search, then accepts a hit only if its `dbXRefs`
    include the seed's curated ontology id (DOID/MeSH). This guards against the
    old behaviour of blindly trusting the top hit, which could silently resolve
    to a narrower or wrong disease. Returns ``(ot_id, "matched")`` on success,
    or ``(None, reason)`` so the caller can route the disease to review.
    """
    expected_curie = ontology_curie(ontology_id)
    if not expected_curie:
        log.error("  No usable seed ontology id for '%s' (got %r) — cannot xref-validate",
                  disease_name, ontology_id)
        return None, "no_seed_ontology_id"

    data = _gql(endpoint, SEARCH_QUERY, {"queryString": disease_name}, cfg, log)
    if not data:
        return None, "search_failed"
    hits = data.get("search", {}).get("hits", [])
    if not hits:
        log.warning("No OT search hits for: %s", disease_name)
        return None, "no_hits"

    match = select_xref_hit(hits, expected_curie)
    if match is None:
        top = hits[0]
        log.error(
            "  XREF MISMATCH for '%s': no hit cross-references %s "
            "(top hit was %s '%s') — rejected to review",
            disease_name, expected_curie, top.get("id"), top.get("name", ""),
        )
        return None, f"no_xref_match:{expected_curie}"

    ot_id = match["id"]
    log.info("  OT: %s -> %s (%s) [xref %s]",
             disease_name, ot_id, match.get("name", ""), expected_curie)
    return ot_id, "matched"


def fetch_associations(efo_id: str, endpoint: str, cfg: dict, log) -> list[dict]:
    page_size = cfg["api"]["page_size"]
    max_pages = cfg["api"]["max_pages"]
    min_score = float(cfg["filtering"]["min_association_score"])

    rows: list[dict] = []
    for page_index in range(max_pages):
        data = _gql(
            endpoint,
            ASSOCIATIONS_QUERY,
            {"efoId": efo_id, "index": page_index, "size": page_size},
            cfg,
            log,
        )
        if not data or not data.get("disease"):
            break
        page_rows = data["disease"]["associatedTargets"]["rows"]
        if not page_rows:
            break

        valid = [r for r in page_rows if r["score"] >= min_score]
        rows.extend(valid)

        # OT returns sorted by score desc — stop once we hit below threshold
        if any(r["score"] < min_score for r in page_rows):
            break

        total = data["disease"]["associatedTargets"]["count"]
        if len(rows) >= total:
            break

    return rows


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _best_uniprot(protein_ids: list[dict]) -> tuple[str, str]:
    swiss = [p for p in protein_ids if p["source"] == "uniprot_swissprot"]
    trembl = [p for p in protein_ids if p["source"] == "uniprot_trembl"]
    if swiss:
        return swiss[0]["id"], "uniprot_swissprot"
    if trembl:
        return trembl[0]["id"], "uniprot_trembl"
    return "", ""


def _flatten(disease_row: dict, efo_id: str, associations: list[dict], retrieved_at: str) -> list[dict]:
    flat = []
    for assoc in associations:
        tgt = assoc["target"]
        uniprot_acc, uniprot_src = _best_uniprot(tgt.get("proteinIds", []))
        flat.append({
            "disease_key":       clean_str(disease_row.get("disease_key") or disease_row.get("canonical_key")),
            "disease_id":        clean_str(disease_row.get("disease_id")),
            "disease_name":      clean_str(disease_row.get("disease_name")),
            "efo_id":            efo_id,
            "ensembl_id":        tgt["id"],
            "gene_symbol":       clean_str(tgt.get("approvedSymbol")),
            "approved_name":     clean_str(tgt.get("approvedName")),
            "uniprot_accession": uniprot_acc,
            "uniprot_source":    uniprot_src,
            "association_score": str(assoc["score"]),
            "retrieved_at":      retrieved_at,
        })
    return flat


def _load_diseases(path: Path) -> list[dict]:
    df = read_frame(path)
    if "disease_key" not in df.columns and "canonical_key" in df.columns:
        df["disease_key"] = df["canonical_key"]
    elif "disease_key" not in df.columns:
        df["disease_key"] = df["disease_name"].apply(make_slug_key)
    # Use standardized_name for search if available
    name_col = "standardized_name" if "standardized_name" in df.columns else "disease_name"
    df["_search_name"] = df[name_col].where(df[name_col].str.strip() != "", df["disease_name"])
    return df.to_dict("records")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def run(cfg: dict, args) -> int:
    log = setup_logging("disease_targets.01_fetch", cfg)

    paths = cfg["paths"]
    diseases_csv = ETL_ROOT / paths["diseases_input"]
    fetch_out    = ETL_ROOT / paths["fetch_out"]
    cache_dir    = ETL_ROOT / paths["cache_dir"]
    endpoint     = cfg["api"]["endpoint"]

    ensure_dir(fetch_out)
    ensure_dir(cache_dir)

    diseases = _load_diseases(diseases_csv)
    log.info("Loaded %d diseases from %s", len(diseases), diseases_csv.name)

    retrieved_at = now_iso()
    all_rows: list[dict] = []
    unresolved: list[dict] = []

    for disease_row in diseases:
        disease_key  = disease_row.get("disease_key") or make_slug_key(disease_row.get("disease_name", ""))
        search_name  = disease_row.get("_search_name") or disease_row.get("disease_name", "")
        cache_file   = cache_dir / f"{disease_key}.json"

        if cache_file.exists() and not args.no_cache:
            log.info("[CACHE] %s", disease_key)
            with open(cache_file, encoding="utf-8") as fh:
                cached = json.load(fh)
            flat = _flatten(disease_row, cached["efo_id"], cached["associations"], cached.get("retrieved_at", retrieved_at))
            all_rows.extend(flat)
            continue

        log.info("Fetching: %s", search_name)
        efo_id, reason = resolve_disease_id(
            search_name, disease_row.get("ontology_id"), endpoint, cfg, log
        )
        if not efo_id:
            log.error("Could not resolve OT disease id for '%s' (%s)", search_name, reason)
            unresolved.append(
                {"disease_key": disease_key, "disease_name": search_name, "reason": reason}
            )
            continue

        associations = fetch_associations(efo_id, endpoint, cfg, log)
        log.info("  %d associations (score >= %.2f)", len(associations), float(cfg["filtering"]["min_association_score"]))

        write_json(
            {"disease_key": disease_key, "disease_name": search_name, "efo_id": efo_id,
             "retrieved_at": retrieved_at, "associations": associations},
            cache_file,
        )

        flat = _flatten(disease_row, efo_id, associations, retrieved_at)
        all_rows.extend(flat)

    if all_rows:
        import pandas as pd
        df = pd.DataFrame(all_rows)
        write_frame(df, fetch_out / "raw_associations.csv")
        log.info("Wrote %d rows to raw_associations.csv", len(df))
    else:
        log.warning("No associations fetched — raw_associations.csv not written.")

    write_json(
        {
            "run_id":                make_run_id("fetch"),
            "diseases_processed":    len(diseases) - len(unresolved),
            "diseases_unresolved":   unresolved,
            "total_associations":    len(all_rows),
            "retrieved_at":          retrieved_at,
        },
        fetch_out / "run_manifest.json",
    )

    if unresolved:
        log.warning("%d disease(s) could not be resolved: %s",
                    len(unresolved), [u["disease_key"] for u in unresolved])

    log.info("Fetch complete.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Fetch disease-target associations from Open Targets")
    parser.add_argument("--input-diseases", type=Path, help="Path to diseases.csv")
    parser.add_argument("--output-dir",     type=Path, help="Output directory")
    parser.add_argument("--cache-dir",      type=Path, help="Cache directory")
    parser.add_argument("--no-cache",       action="store_true", help="Re-fetch ignoring cache")
    parser.add_argument("--dry-run",        action="store_true", help="Print resolved config and exit")
    args = parser.parse_args()

    cfg = load_settings("disease_targets")

    # CLI overrides
    if args.input_diseases:
        cfg["paths"]["diseases_input"] = str(args.input_diseases)
    if args.output_dir:
        cfg["paths"]["fetch_out"] = str(args.output_dir)
    if args.cache_dir:
        cfg["paths"]["cache_dir"] = str(args.cache_dir)

    if args.dry_run:
        import json as _json
        print(_json.dumps(cfg, indent=2, default=str))
        sys.exit(0)

    sys.exit(run(cfg, args))
