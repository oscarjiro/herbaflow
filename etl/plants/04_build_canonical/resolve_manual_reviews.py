"""
Fetches full GBIF metadata for manually verified UsageKeys.
"""

import pandas as pd
import requests
from pathlib import Path

# Config - matching your ETL structure
INPUT_MAP = Path("out/manual_review_decisions.csv")
OUTPUT_PATH = Path("out/manually_accepted_review_plants.csv")
GBIF_API = "https://api.gbif.org/v1/species/"


def fetch_gbif_details(usage_key):
    try:
        resp = requests.get(f"{GBIF_API}{usage_key}", timeout=20)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        print(f"Error fetching {usage_key}: {e}")
        return None


def main():
    if not INPUT_MAP.exists():
        print(f"File not found: {INPUT_MAP}")
        return

    df_map = pd.read_csv(INPUT_MAP)
    resolved_rows = []

    print(f"🚀 Resolving {len(df_map)} manual decisions via GBIF...")

    for _, row in df_map.iterrows():
        input_name = row["input_name"]
        gbif_id = int(row["gbif_id"])

        data = fetch_gbif_details(gbif_id)
        if not data:
            continue

        # Handle Synonyms: If the manual ID is a synonym, we want the accepted info
        # GBIF provides 'acceptedUsageKey' and 'accepted' (the name)
        accepted_usage_key = data.get("acceptedUsageKey", data.get("key"))

        # Build the "Big Shape" row
        resolved_rows.append(
            {
                "decision": "accepted",
                "decision_reason": "Manually verified species-level match after review.",
                "source_name": "KNApSAcK World",
                "canonical_scientific_name": data.get("scientificName"),
                "authorship": data.get("authorship", ""),
                "input_name": input_name,
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
    out_df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")
    print(f"✅ Success! Saved {len(out_df)} rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
