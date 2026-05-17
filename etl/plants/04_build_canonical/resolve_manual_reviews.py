"""
Fetches full GBIF metadata for manually verified UsageKeys.
"""

from __future__ import annotations
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging

import pandas as pd
import requests

GBIF_API = "https://api.gbif.org/v1/species/"


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


def fetch_gbif_details(usage_key, timeout: float = 30):
    try:
        resp = requests.get(f"{GBIF_API}{usage_key}", timeout=timeout)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return None, e


def main() -> None:
    cfg = load_settings("plants")
    log = shared_setup_logging("plants.resolve_manual_reviews", cfg)
    input_map, output_path, timeout, source_name = _config()

    if not input_map.exists():
        log.error("File not found: %s", input_map)
        return

    df_map = pd.read_csv(input_map)
    resolved_rows = []

    log.info("Resolving %d manual decisions via GBIF...", len(df_map))

    for _, row in df_map.iterrows():
        input_name = row["input_name"]
        gbif_id = int(row["gbif_id"])
        raw_plant_id = row["raw_plant_id"]

        result = fetch_gbif_details(gbif_id, timeout=timeout)
        if isinstance(result, tuple):
            data, err = result
            log.error("Error fetching %s: %s", gbif_id, err)
            continue
        data = result

        if not data:
            log.error("No data returned for usage key: %s", gbif_id)
            continue

        # Handle Synonyms: If the manual ID is a synonym, we want the accepted info
        # GBIF provides 'acceptedUsageKey' and 'accepted' (the name)
        accepted_usage_key = data.get("acceptedUsageKey", data.get("key"))

        # Build the "Big Shape" row
        resolved_rows.append(
            {
                "decision": "accepted",
                "decision_reason": "Manually verified species-level match after review.",
                "source_name": source_name,
                "canonical_scientific_name": data.get("scientificName"),
                "authorship": data.get("authorship", ""),
                "input_name": input_name,
                "raw_plant_id": raw_plant_id,
                "canonical_lookup_key": input_name.lower().strip(),
                "source_row_count": 1,
                "query_status": "ok",
                "http_status": 200,
                "error_message": "",
                "matched_name": data.get("scientificName"),
                "accepted_name": data.get("accepted", data.get("scientificName")),
                "rank": data.get("rank"),
                "taxonomic_status": data.get("taxonomicStatus"),
                "match_type": "MANUAL",
                "confidence": 100,
                "gbif_usage_key": data.get("key"),
                "gbif_accepted_usage_key": accepted_usage_key,
                "gbif_species_key": data.get("speciesKey", ""),
                "gbif_genus_key": data.get("genusKey", ""),
                "gbif_family_key": data.get("familyKey", ""),
                "gbif_kingdom_key": data.get("kingdomKey", ""),
                "cache_key": "manual_override",
                "cache_path": "manual",
            }
        )

    # Save to the specific file Part 2 is looking for
    out_df = pd.DataFrame(resolved_rows)
    out_df.to_csv(output_path, index=False, encoding="utf-8-sig")
    log.info("Success. Saved %d rows to %s", len(out_df), output_path)


if __name__ == "__main__":
    main()
