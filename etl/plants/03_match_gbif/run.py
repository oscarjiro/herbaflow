"""
03_match_gbif: match normalized plant names against the GBIF taxonomy API.

Input:
    02_normalize_taxonomy/out/normalized_plants.csv

Outputs:
    03_match_gbif/out/gbif_matches.csv
    03_match_gbif/out/cache/<deterministic-cache-key>.json
    03_match_gbif/out/match_gbif.log

This script:
- reads unique normalized plant names from the normalized staging file
- queries GBIF's species match API using requests
- caches each unique query response locally
- avoids re-querying names that are already cached
- stores the full GBIF JSON response for each query
- writes a tabular match result file for downstream ETL steps
- handles rate limiting and request failures with retries and backoff

Run:
    python match_gbif.py \
        --input 02_normalize_taxonomy/out/normalized_plants.csv \
        --cache-dir 03_match_gbif/out/cache \
        --output 03_match_gbif/out/gbif_matches.csv \
        --user-agent "thesis-etl/1.0 (your-email@example.com)"
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir

import argparse
import hashlib
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Sequence, Tuple

import pandas as pd
import requests


def _defaults() -> tuple[Path, Path, Path, str, float, int, float, float]:
    cfg = load_settings("plants")
    step = cfg["paths"]["match_gbif"]
    api = cfg.get("gbif", {}).get("api", {})
    return (
        ETL_ROOT / step["input"],
        ETL_ROOT / step["cache_dir"],
        ETL_ROOT / step["output_dir"] / step["output_file"],
        step["log_file"],
        float(api.get("timeout_seconds", 30)),
        int(api.get("max_retries", 5)),
        float(api.get("backoff_base_seconds", 1.5)),
        float(api.get("backoff_max_seconds", 60.0)),
    )

GBIF_MATCH_URL = "https://api.gbif.org/v2/species/match"

NAME_CANDIDATE_COLUMNS = (
    "canonical_candidate_name",
    "verbatim_scientific_name",
    "original_species_name",
    "species_name",
)

WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class MatchStats:
    total_input_rows: int
    unique_queries: int
    cache_hits: int
    cache_misses: int
    successful_matches: int
    failed_matches: int
    output_rows: int


def parse_args() -> argparse.Namespace:
    (
        default_input,
        default_cache_dir,
        default_output,
        default_log_file,
        default_timeout,
        default_max_retries,
        default_backoff_base,
        default_backoff_max,
    ) = _defaults()
    parser = argparse.ArgumentParser(
        description="Query GBIF species matching API for unique normalized plant names."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Path to normalized input CSV (default: plants/02_normalize_taxonomy/out/normalized_plants.csv)",
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=default_cache_dir,
        help="Directory for cached GBIF JSON responses (default: plants/03_match_gbif/out/cache)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=default_output,
        help="Path to output CSV (default: plants/03_match_gbif/out/gbif_matches.csv)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=default_log_file,
        help="Log filename written next to the output (default: match_gbif.log)",
    )
    parser.add_argument(
        "--user-agent",
        type=str,
        default="",
        # required=True,
        help="HTTP User-Agent header value, preferably including a URL or email address.",
    )
    parser.add_argument(
        "--checklist-key",
        type=str,
        default="",
        help="Optional GBIF checklistKey for matching against a specific taxonomy.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=default_timeout,
        help=f"HTTP timeout in seconds (default: {default_timeout}, from gbif.api.timeout_seconds)",
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=default_max_retries,
        help=f"Maximum retry attempts for transient failures (default: {default_max_retries}, from gbif.api.max_retries)",
    )
    parser.add_argument(
        "--backoff-base",
        type=float,
        default=default_backoff_base,
        help=f"Base backoff seconds for retries (default: {default_backoff_base}, from gbif.api.backoff_base_seconds)",
    )
    parser.add_argument(
        "--backoff-max",
        type=float,
        default=default_backoff_max,
        help=f"Maximum backoff seconds for retries (default: {default_backoff_max}, from gbif.api.backoff_max_seconds)",
    )
    return parser.parse_args()



def load_input(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path, dtype=str, keep_default_na=False, na_filter=False)
    return df


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def canonicalize_query_name(value: Any) -> str:
    return normalize_text(value)


def build_lookup_table(df: pd.DataFrame) -> pd.DataFrame:
    """
    Build a unique query table from the most specific normalized name available.
    """
    source_cols = [c for c in NAME_CANDIDATE_COLUMNS if c in df.columns]
    if not source_cols:
        raise ValueError(
            "No usable name columns found. Expected one of: "
            + ", ".join(NAME_CANDIDATE_COLUMNS)
        )

    # Select the first non-empty usable column per row.
    def pick_name(row: pd.Series) -> str:
        for col in source_cols:
            value = canonicalize_query_name(row.get(col, ""))
            if value:
                return value
        return ""

    work = df.copy()
    work["input_name"] = work.apply(pick_name, axis=1)
    if "canonical_lookup_key" in work.columns:
        work["canonical_lookup_key"] = work["canonical_lookup_key"].map(normalize_text)
    else:
        work["canonical_lookup_key"] = work["input_name"].map(
            canonical_lookup_key_from_text
        )

    work = work.loc[work["input_name"].ne("")].copy()

    if work.empty:
        raise ValueError("No valid names found to query against GBIF.")

    if "plant_id" not in work.columns:
        work["plant_id"] = ""

    # Deduplicate by canonical lookup key; keep the first observed display name.
    grouped = (
        work.groupby("canonical_lookup_key", as_index=False)
        .agg(
            input_name=("input_name", "first"),
            raw_plant_id=("plant_id", "first"),
            source_row_count=("input_name", "size"),
        )
        .sort_values(["input_name", "canonical_lookup_key"], kind="stable")
        .reset_index(drop=True)
    )
    return grouped


def canonical_lookup_key_from_text(value: Any) -> str:
    text = normalize_text(value).lower()
    text = re.sub(r"[^a-z0-9\s]+", " ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def stable_cache_key(payload: Dict[str, Any]) -> str:
    """
    Deterministic cache key derived from the input query payload.
    """
    normalized_payload = json.dumps(
        payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    )
    return hashlib.sha256(normalized_payload.encode("utf-8")).hexdigest()


def cache_path_for_key(cache_dir: Path, cache_key: str) -> Path:
    return cache_dir / f"{cache_key}.json"


def load_cached_response(cache_path: Path) -> Optional[Dict[str, Any]]:
    if not cache_path.exists():
        return None
    try:
        with cache_path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        logging.warning(
            "Cache file exists but could not be read; treating as cache miss: %s",
            cache_path,
        )
        return None


def write_cached_response(cache_path: Path, payload: Dict[str, Any]) -> None:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    with cache_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)


def gbif_request(
    session: requests.Session,
    scientific_name: str,
    checklist_key: str,
    timeout: float,
) -> requests.Response:
    params: Dict[str, str] = {"scientificName": scientific_name}
    if checklist_key:
        params["checklistKey"] = checklist_key
    return session.get(GBIF_MATCH_URL, params=params, timeout=timeout)


def request_with_retries(
    session: requests.Session,
    scientific_name: str,
    checklist_key: str,
    timeout: float,
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
) -> Tuple[Optional[Dict[str, Any]], int, Optional[str]]:
    """
    Return (json_payload, http_status, error_message).
    """
    last_error: Optional[str] = None

    for attempt in range(max_retries + 1):
        try:
            response = gbif_request(session, scientific_name, checklist_key, timeout)
            status = response.status_code

            if status == 200:
                try:
                    return response.json(), status, None
                except Exception as exc:
                    return None, status, f"Invalid JSON response: {exc}"

            if status == 429 or 500 <= status < 600:
                retry_after = response.headers.get("Retry-After", "").strip()
                if retry_after.isdigit():
                    sleep_seconds = min(float(retry_after), backoff_max)
                else:
                    sleep_seconds = min(backoff_base * (2**attempt), backoff_max)
                    sleep_seconds += random.uniform(0.0, 0.25)

                last_error = f"HTTP {status}: {response.text[:500]}"
                if attempt < max_retries:
                    logging.warning(
                        "Transient GBIF error for '%s' (attempt %d/%d, status=%d). Retrying in %.2fs.",
                        scientific_name,
                        attempt + 1,
                        max_retries + 1,
                        status,
                        sleep_seconds,
                    )
                    time.sleep(sleep_seconds)
                    continue
                return None, status, last_error

            # Non-retryable 4xx errors.
            try:
                payload = response.json()
                message = json.dumps(payload, ensure_ascii=False)
            except Exception:
                message = response.text[:500]
            return None, status, f"HTTP {status}: {message}"

        except requests.RequestException as exc:
            last_error = str(exc)
            if attempt < max_retries:
                sleep_seconds = min(backoff_base * (2**attempt), backoff_max)
                sleep_seconds += random.uniform(0.0, 0.25)
                logging.warning(
                    "Request error for '%s' (attempt %d/%d): %s. Retrying in %.2fs.",
                    scientific_name,
                    attempt + 1,
                    max_retries + 1,
                    exc,
                    sleep_seconds,
                )
                time.sleep(sleep_seconds)
                continue
            return None, 0, last_error

    return None, 0, last_error


def get_rank_key(classification: Sequence[Dict[str, Any]], target_rank: str) -> str:
    target_rank = target_rank.upper()
    for node in classification:
        node_rank = normalize_text(node.get("rank", "")).upper()
        if node_rank == target_rank:
            key = node.get("key", "")
            return "" if key is None else str(key)
    return ""


def get_rank_name(classification: Sequence[Dict[str, Any]], target_rank: str) -> str:
    target_rank = target_rank.upper()
    for node in classification:
        node_rank = normalize_text(node.get("rank", "")).upper()
        if node_rank == target_rank:
            name = node.get("name", "")
            return "" if name is None else normalize_text(name)
    return ""


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = normalize_text(value)
        if text:
            return text
    return ""


def parse_match_record(
    input_name: str,
    raw_plant_id: str,
    canonical_lookup_key: str,
    source_row_count: int,
    cache_key: str,
    cache_path: Path,
    response_json: Optional[Dict[str, Any]],
    http_status: int,
    error_message: Optional[str],
) -> Dict[str, Any]:
    """
    Convert one GBIF response into a flat table row.
    """
    if not response_json:
        return {
            "input_name": input_name,
            "raw_plant_id": raw_plant_id,
            "canonical_lookup_key": canonical_lookup_key,
            "source_row_count": source_row_count,
            "cache_key": cache_key,
            "cache_path": str(cache_path),
            "query_status": "error",
            "http_status": http_status,
            "error_message": error_message or "",
            "matched_name": "",
            "accepted_name": "",
            "authorship": "",
            "rank": "",
            "taxonomic_status": "",
            "match_type": "",
            "confidence": "",
            "gbif_usage_key": "",
            "gbif_accepted_usage_key": "",
            "gbif_species_key": "",
            "gbif_genus_key": "",
            "gbif_family_key": "",
            "gbif_kingdom_key": "",
            "family_name": "",
        }

    usage = response_json.get("usage") or {}
    accepted = (
        response_json.get("acceptedUsage")
        or response_json.get("acceptedUsageKey")
        or {}
    )
    diagnostics = response_json.get("diagnostics") or {}

    classification = response_json.get("classification") or []
    if not isinstance(classification, list):
        classification = []

    matched_name = first_non_empty(
        usage.get("name"),
        response_json.get("scientificName"),
    )
    accepted_name = first_non_empty(
        accepted.get("name") if isinstance(accepted, dict) else "",
        usage.get("name"),
        response_json.get("scientificName"),
    )
    authorship = first_non_empty(
        usage.get("authorship"),
        accepted.get("authorship") if isinstance(accepted, dict) else "",
        response_json.get("authorship"),
    )
    rank = first_non_empty(
        usage.get("rank"),
        response_json.get("rank"),
    )
    taxonomic_status = first_non_empty(
        response_json.get("taxonomicStatus"),
        usage.get("status"),
        accepted.get("status") if isinstance(accepted, dict) else "",
    )
    match_type = first_non_empty(
        diagnostics.get("matchType"),
        response_json.get("matchType"),
    )
    confidence = diagnostics.get("confidence")
    if confidence is None:
        confidence = response_json.get("confidence")

    gbif_usage_key = first_non_empty(usage.get("key"), response_json.get("usageKey"))
    gbif_accepted_usage_key = first_non_empty(
        accepted.get("key") if isinstance(accepted, dict) else "",
        response_json.get("acceptedUsageKey"),
        gbif_usage_key,
    )

    gbif_species_key = get_rank_key(classification, "SPECIES")
    gbif_genus_key = get_rank_key(classification, "GENUS")
    gbif_family_key = get_rank_key(classification, "FAMILY")
    gbif_kingdom_key = get_rank_key(classification, "KINGDOM")
    family_name = get_rank_name(classification, "FAMILY")

    return {
        "input_name": input_name,
        "raw_plant_id": raw_plant_id,
        "canonical_lookup_key": canonical_lookup_key,
        "source_row_count": source_row_count,
        "cache_key": cache_key,
        "cache_path": str(cache_path),
        "query_status": "ok",
        "http_status": http_status,
        "error_message": error_message or "",
        "matched_name": matched_name,
        "accepted_name": accepted_name,
        "authorship": authorship,
        "rank": rank,
        "taxonomic_status": taxonomic_status,
        "match_type": match_type,
        "confidence": confidence if confidence is not None else "",
        "gbif_usage_key": gbif_usage_key,
        "gbif_accepted_usage_key": gbif_accepted_usage_key,
        "gbif_species_key": gbif_species_key,
        "gbif_genus_key": gbif_genus_key,
        "gbif_family_key": gbif_family_key,
        "gbif_kingdom_key": gbif_kingdom_key,
        "family_name": family_name,
    }


def query_gbif_matches(
    query_table: pd.DataFrame,
    cache_dir: Path,
    user_agent: str,
    checklist_key: str,
    timeout: float,
    max_retries: int,
    backoff_base: float,
    backoff_max: float,
) -> Tuple[List[Dict[str, Any]], MatchStats]:
    session = requests.Session()
    session.headers.update(
        {
            "User-Agent": user_agent,
            "Accept": "application/json",
        }
    )

    rows: List[Dict[str, Any]] = []
    cache_hits = 0
    cache_misses = 0
    successful_matches = 0
    failed_matches = 0

    ensure_dir(cache_dir)

    for _, record in query_table.iterrows():
        input_name = normalize_text(record["input_name"])
        raw_plant_id = normalize_text(record.get("raw_plant_id", ""))
        canonical_lookup_key = normalize_text(record["canonical_lookup_key"])
        source_row_count = int(record["source_row_count"])

        payload = {
            "endpoint": GBIF_MATCH_URL,
            "scientificName": input_name,
            "checklistKey": checklist_key or "",
        }
        cache_key = stable_cache_key(payload)
        cache_path = cache_path_for_key(cache_dir, cache_key)

        cached = load_cached_response(cache_path)
        if cached is not None:
            cache_hits += 1
            response_json = cached
            http_status = int(
                cached.get(
                    "_http_status",
                    200 if "usage" in cached or "matchType" in cached else 0,
                )
            )
            error_message = cached.get("_error_message", "")
        else:
            cache_misses += 1
            response_json, http_status, error_message = request_with_retries(
                session=session,
                scientific_name=input_name,
                checklist_key=checklist_key,
                timeout=timeout,
                max_retries=max_retries,
                backoff_base=backoff_base,
                backoff_max=backoff_max,
            )

            # Cache both success and failure envelopes so reruns are deterministic.
            cache_payload: Dict[str, Any]
            if response_json is not None:
                cache_payload = dict(response_json)
                cache_payload["_http_status"] = http_status
                cache_payload["_error_message"] = error_message or ""
            else:
                cache_payload = {
                    "_http_status": http_status,
                    "_error_message": error_message or "",
                    "input_name": input_name,
                    "checklistKey": checklist_key or "",
                }
            write_cached_response(cache_path, cache_payload)
            if response_json is None:
                # Keep the cache payload in memory for downstream parsing as well.
                response_json = cache_payload

        row = parse_match_record(
            input_name=input_name,
            raw_plant_id=raw_plant_id,
            canonical_lookup_key=canonical_lookup_key,
            source_row_count=source_row_count,
            cache_key=cache_key,
            cache_path=cache_path,
            response_json=response_json,
            http_status=http_status,
            error_message=error_message,
        )

        if row["query_status"] == "ok" and row["matched_name"]:
            successful_matches += 1
        else:
            failed_matches += 1

        rows.append(row)

    stats = MatchStats(
        total_input_rows=(
            int(query_table["source_row_count"].sum()) if not query_table.empty else 0
        ),
        unique_queries=len(query_table),
        cache_hits=cache_hits,
        cache_misses=cache_misses,
        successful_matches=successful_matches,
        failed_matches=failed_matches,
        output_rows=len(rows),
    )
    return rows, stats


def write_output(rows: List[Dict[str, Any]], output_path: Path) -> None:
    ensure_dir(output_path.parent)

    df = pd.DataFrame(rows)

    preferred_order = [
        "input_name",
        "raw_plant_id",
        "canonical_lookup_key",
        "source_row_count",
        "query_status",
        "http_status",
        "error_message",
        "matched_name",
        "accepted_name",
        "authorship",
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
    ordered_cols = [c for c in preferred_order if c in df.columns] + [
        c for c in df.columns if c not in preferred_order
    ]
    df = df[ordered_cols]

    df.to_csv(output_path, index=False, encoding="utf-8")


def main() -> int:
    args = parse_args()
    cfg = load_settings("plants")
    log = shared_setup_logging("plants.03_match_gbif", cfg)
    ensure_dir(args.output.parent)

    log.info("Starting 03_match_gbif")
    log.info("Log file: %s", args.output.parent / args.log_file)

    try:
        df = load_input(args.input)
        query_table = build_lookup_table(df)

        log.info("Loaded %d input rows from %s", len(df), args.input)
        log.info("Built %d unique GBIF queries", len(query_table))

        rows, stats = query_gbif_matches(
            query_table=query_table,
            cache_dir=args.cache_dir,
            user_agent=args.user_agent,
            checklist_key=args.checklist_key,
            timeout=args.timeout,
            max_retries=args.max_retries,
            backoff_base=args.backoff_base,
            backoff_max=args.backoff_max,
        )

        write_output(rows, args.output)

        log.info("Wrote match table: %s", args.output)
        log.info(
            "Done. input_rows=%d unique_queries=%d cache_hits=%d cache_misses=%d successful_matches=%d failed_matches=%d output_rows=%d",
            stats.total_input_rows,
            stats.unique_queries,
            stats.cache_hits,
            stats.cache_misses,
            stats.successful_matches,
            stats.failed_matches,
            stats.output_rows,
        )
        return 0

    except Exception as exc:
        logging.exception("GBIF matching failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
