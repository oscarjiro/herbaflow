"""
Resolve curator manual-review decisions into canonical-ready rows.

Reads manual_review_decisions.csv (input_name, gbif_id, raw_plant_id) - one row per
review case a human resolved to a specific GBIF usage key - fetches full GBIF metadata
for each key, and writes manually_accepted_review_plants.csv in the same shape as
accepted_plants.csv so 04_build_canonical/run_part2.py can merge them into the final
plants/plant_aliases seed files.

Run as part of the pipeline (main.py orders it after build_canonical_part1 and before
build_canonical_part2) or standalone:

    python resolve_manual_reviews.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from typing import Any, Dict, Optional

import pandas as pd
import requests
from shared.utils import ETL_ROOT, load_settings
from shared.utils import setup_logging as shared_setup_logging

GBIF_API = "https://api.gbif.org/v1/species/"

# Columns emitted for each resolved row. Kept aligned with accepted_plants.csv so
# part 2's common-column merge preserves every field.
RESOLVED_COLUMNS = [
    "decision",
    "decision_reason",
    "source_name",
    "canonical_scientific_name",
    "authorship",
    "input_name",
    "raw_plant_id",
    "canonical_lookup_key",
    "source_row_count",
    "query_status",
    "http_status",
    "error_message",
    "matched_name",
    "accepted_name",
    "rank",
    "taxonomic_status",
    "match_type",
    "confidence",
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
    "family_name",
    "cache_key",
    "cache_path",
]


def _config() -> tuple[Path, Path, float, str]:
    cfg = load_settings("plants")
    step = cfg["paths"]["build_canonical_part1"]
    out_dir = ETL_ROOT / step["output_dir"]
    timeout = float(cfg.get("gbif", {}).get("api", {}).get("timeout_seconds", 30))
    source_name = cfg.get("source", {}).get("name", "KNApSAcK World")
    return (
        out_dir / "manual_review_decisions.csv",
        out_dir / "manually_accepted_review_plants.csv",
        timeout,
        source_name,
    )


def fetch_gbif_details(usage_key: Any, timeout: float = 30):
    try:
        resp = requests.get(f"{GBIF_API}{usage_key}", timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None, e


def build_resolved_row(
    data: Dict[str, Any],
    input_name: str,
    raw_plant_id: Any,
    source_name: str,
) -> Dict[str, Any]:
    """Turn one GBIF /v1/species/{key} response into a canonical-ready row.

    The curator may point at a synonym usage key. In that case GBIF returns the
    accepted name in ``accepted`` and the accepted taxon's key in ``acceptedKey``
    (the v1 API uses ``acceptedKey``; ``acceptedUsageKey`` is null there). We store
    the ACCEPTED name/key so this row's identity (plant_id/canonical_key, both built
    off gbif_accepted_usage_key in part 2) matches the automated path, which prefers
    the accepted name over the matched name. The chosen usage's own name is retained
    as ``matched_name`` so it still becomes a synonym alias downstream.
    """
    own_name = (data.get("scientificName") or "").strip()
    accepted_name = (data.get("accepted") or own_name).strip()

    own_key = data.get("key")
    accepted_key = data.get("acceptedKey") or data.get("acceptedUsageKey") or own_key

    return {
        "decision": "accepted",
        "decision_reason": "Manually verified species-level match after review.",
        "source_name": source_name,
        # Accepted-name-first, mirroring choose_canonical_scientific_name in part 1.
        "canonical_scientific_name": accepted_name,
        "authorship": data.get("authorship") or "",
        "input_name": input_name,
        "raw_plant_id": raw_plant_id,
        "canonical_lookup_key": str(input_name).lower().strip(),
        "source_row_count": 1,
        "query_status": "ok",
        "http_status": 200,
        "error_message": "",
        "matched_name": own_name,
        "accepted_name": accepted_name,
        "rank": data.get("rank") or "",
        "taxonomic_status": data.get("taxonomicStatus") or "",
        "match_type": "MANUAL",
        "confidence": 100,
        "gbif_usage_key": own_key,
        "gbif_accepted_usage_key": accepted_key,
        "gbif_species_key": data.get("speciesKey", ""),
        "gbif_genus_key": data.get("genusKey", ""),
        "gbif_family_key": data.get("familyKey", ""),
        "gbif_kingdom_key": data.get("kingdomKey", ""),
        "family_name": data.get("family") or "",
        "cache_key": "manual_override",
        "cache_path": "manual",
    }


def main() -> None:
    cfg = load_settings("plants")
    log = shared_setup_logging("plants.resolve_manual_reviews", cfg)
    input_map, output_path, timeout, source_name = _config()

    if not input_map.exists():
        log.warning(
            "No manual review decisions file at %s; leaving %s untouched.",
            input_map,
            output_path,
        )
        return

    df_map = pd.read_csv(input_map, dtype=str, keep_default_na=False, na_filter=False)
    resolved_rows = []

    log.info("Resolving %d manual decisions via GBIF...", len(df_map))

    for _, row in df_map.iterrows():
        input_name = row["input_name"]
        gbif_id = int(row["gbif_id"])
        raw_plant_id = row["raw_plant_id"]

        result = fetch_gbif_details(gbif_id, timeout=timeout)
        if isinstance(result, tuple):
            _, err = result
            log.error("Error fetching %s: %s", gbif_id, err)
            continue
        data: Optional[Dict[str, Any]] = result

        if not data:
            log.error("No data returned for usage key: %s", gbif_id)
            continue

        resolved_rows.append(
            build_resolved_row(data, input_name, raw_plant_id, source_name)
        )

    if not resolved_rows:
        # Never clobber an existing populated file with an empty result (e.g. a
        # transient GBIF outage); leave prior curator work in place.
        log.error(
            "Resolved 0 rows; leaving %s untouched to avoid losing prior work.",
            output_path,
        )
        return

    out_df = pd.DataFrame(resolved_rows, columns=RESOLVED_COLUMNS)
    out_df.to_csv(output_path, index=False, encoding="utf-8")
    log.info("Success. Saved %d rows to %s", len(out_df), output_path)


if __name__ == "__main__":
    main()
