"""
01_fetch/run.py — Fetch disease-target associations from Open Targets Platform.

For each canonical disease:
  1. Resolve EFO ID via OT search (using disease_name)
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
from shared.utils import ETL_ROOT, load_settings, setup_logging, ensure_dir, now_iso, make_run_id, write_json
from disease_targets.utils import read_frame, write_frame, make_slug_key, clean_str

# ---------------------------------------------------------------------------
# GraphQL queries
# ---------------------------------------------------------------------------

SEARCH_QUERY = """
query SearchDisease($queryString: String!) {
  search(queryString: $queryString, entityNames: ["disease"], page: {index: 0, size: 5}) {
    hits {
      id
      name
      entity
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


def resolve_efo_id(disease_name: str, endpoint: str, cfg: dict, log) -> str | None:
    data = _gql(endpoint, SEARCH_QUERY, {"queryString": disease_name}, cfg, log)
    if not data:
        return None
    hits = data.get("search", {}).get("hits", [])
    if not hits:
        log.warning("No OT search hits for: %s", disease_name)
        return None
    efo_id = hits[0]["id"]
    log.info("  EFO: %s -> %s (%s)", disease_name, efo_id, hits[0].get("name", ""))
    return efo_id


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
        efo_id = resolve_efo_id(search_name, endpoint, cfg, log)
        if not efo_id:
            log.error("Could not resolve EFO ID for: %s", search_name)
            unresolved.append({"disease_key": disease_key, "disease_name": search_name})
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
