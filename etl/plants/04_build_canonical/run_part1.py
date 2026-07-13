"""
04_build_canonical (part 1): classify GBIF match rows into accepted, review, or rejected.

Input:
    GBIF match output CSV from 03_match_gbif/out/

Outputs:
    04_build_canonical/out/accepted_plants.csv
    04_build_canonical/out/review_plants.csv
    04_build_canonical/out/rejected_plants.csv
    04_build_canonical/out/build_canonical_report.txt
    04_build_canonical/out/build_canonical.log

This step:
- reads GBIF match rows
- applies deterministic acceptance rules based on match_type and confidence
- preserves all original input columns and match metadata
- adds decision and decision_reason
- corrects schema fields needed later in the pipeline
- keeps manual-review rows instead of dropping them

Run:
    python build_canonical_part1.py \
        --input 03_match_gbif/out/gbif_matches.csv \
        --output-dir 04_build_canonical/out
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
import argparse
import logging
import math
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
from shared.utils import ETL_ROOT, ensure_dir, load_settings
from shared.utils import setup_logging as shared_setup_logging

DEFAULT_SOURCE_NAME = "KNApSAcK World"


def _defaults() -> dict:
    cfg = load_settings("plants")
    return cfg["paths"]["build_canonical_part1"]


def _thresholds() -> tuple[float, float, float]:
    cfg = load_settings("plants")
    rules = cfg.get("gbif", {}).get("accept_rules", {})
    return (
        float(rules.get("accept_min_confidence", 90.0)),
        float(rules.get("review_min_confidence", 70.0)),
        float(rules.get("higherrank_review_min_confidence", 80.0)),
    )


def _plantae_kingdom_key() -> str:
    cfg = load_settings("plants")
    rules = cfg.get("gbif", {}).get("accept_rules", {})
    return str(rules.get("plantae_kingdom_key", "6")).strip()

GBIF_ID_FIELDS = [
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
    "gbif_taxon_key",
    "gbif_accepted_key",
    "usageKey",
    "acceptedUsageKey",
    "speciesKey",
    "genusKey",
    "familyKey",
    "kingdomKey",
]

ACCEPTED_MATCH_TYPES = {"EXACT", "VARIANT"}
REVIEW_MATCH_TYPES = {
    "EXACT",
    "VARIANT",
    "FUZZY",
    "HIGHERRANK",
    "HIGHER_RANK",
    "HIGHER-RANK",
}
ACCEPTED_TAXONOMIC_STATUSES = {"ACCEPTED", "SYNONYM"}

ACCEPT_CONFIDENCE_THRESHOLD, REVIEW_CONFIDENCE_THRESHOLD, HIGHERRANK_REVIEW_THRESHOLD = _thresholds()

# GBIF taxon key for kingdom Plantae. A match whose resolved kingdom key is
# present and differs from this is a non-plant (e.g. a fungus or animal) and is
# rejected before it can reach the canonical plant table.
PLANTAE_KINGDOM_KEY = _plantae_kingdom_key()

WHITESPACE_RE = re.compile(r"\s+")


@dataclass(frozen=True)
class BuildCanonicalResult:
    input_rows: int
    accepted_rows: int
    review_rows: int
    rejected_rows: int
    output_dir: Path
    accepted_path: Path
    review_path: Path
    rejected_path: Path
    report_path: Path
    log_path: Path


def parse_args() -> argparse.Namespace:
    step = _defaults()
    parser = argparse.ArgumentParser(
        description="Classify GBIF matched plant rows into accepted, review, or rejected."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ETL_ROOT / step["input"],
        help="Path to GBIF match output CSV (default: plants/03_match_gbif/out/gbif_matches.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ETL_ROOT / step["output_dir"],
        help="Directory where canonical outputs will be written (default: plants/04_build_canonical/out)",
    )
    parser.add_argument(
        "--accepted-file",
        type=str,
        default=step["accepted_file"],
        help="Accepted output filename (default: accepted_plants.csv)",
    )
    parser.add_argument(
        "--review-file",
        type=str,
        default=step["review_file"],
        help="Review output filename (default: review_plants.csv)",
    )
    parser.add_argument(
        "--rejected-file",
        type=str,
        default=step["rejected_file"],
        help="Rejected output filename (default: rejected_plants.csv)",
    )
    parser.add_argument(
        "--manually-accepted-review-file",
        type=str,
        default=step["manually_accepted_review_file"],
        help="Manually accepted output filename (default: manually_accepted_review_plants.csv)",
    )
    parser.add_argument(
        "--report-file",
        type=str,
        default=step["report_file"],
        help="Summary report filename (default: build_canonical_report.txt)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=step["log_file"],
        help="Log filename (default: build_canonical.log)",
    )
    parser.add_argument(
        "--source-name",
        type=str,
        default=DEFAULT_SOURCE_NAME,
        help='Source system name to use when source_name is missing (default: "KNApSAcK World")',
    )
    return parser.parse_args()



def load_input(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    return pd.read_csv(input_path, dtype=str, keep_default_na=False, na_filter=False)


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_id_like(value: Any) -> str:
    """
    Convert GBIF identifier-like values to stable plain strings without .0 suffixes.
    """
    text = normalize_text(value)
    if not text:
        return ""

    lower = text.lower()
    if lower in {"nan", "none", "null"}:
        return ""

    # Clean obvious float-like text.
    try:
        num = float(text)
        if math.isfinite(num) and num.is_integer():
            return str(int(num))
        # Keep non-integer numeric values as compact strings without trailing zeros.
        return format(num, ".15g")
    except Exception:
        pass

    # If the text is an integer in string form with padding, strip padding safely.
    if re.fullmatch(r"[+-]?\d+", text):
        return str(int(text))
    return text


def parse_confidence(value: Any) -> Optional[float]:
    text = normalize_text(value)
    if not text:
        return None
    try:
        return float(text)
    except Exception:
        return None


def normalize_match_type(value: Any) -> str:
    text = normalize_text(value).upper().replace(" ", "_").replace("-", "_")
    return text


def normalize_taxonomic_status(value: Any) -> str:
    return normalize_text(value).upper().replace(" ", "_").replace("-", "_")


def determine_decision(row: pd.Series) -> Tuple[str, str]:
    """
    Deterministic classification:
    - accepted: exact GBIF match, high confidence, and taxonomic status is acceptable
    - review: plausible match but not strong enough for fully automated acceptance
    - rejected: failed query, no match, or weak/ambiguous match
    """
    query_status = normalize_text(row.get("query_status", "")).lower()
    match_type = normalize_match_type(row.get("match_type", ""))
    taxonomic_status = normalize_taxonomic_status(row.get("taxonomic_status", ""))
    confidence = parse_confidence(row.get("confidence", ""))

    matched_name = normalize_text(row.get("matched_name", ""))
    accepted_name = normalize_text(row.get("accepted_name", ""))
    http_status = normalize_text(row.get("http_status", ""))
    error_message = normalize_text(row.get("error_message", ""))

    if query_status and query_status != "ok":
        reason = f"Rejected because GBIF query status was '{query_status}'."
        if http_status:
            reason += f" HTTP status: {http_status}."
        if error_message:
            reason += f" Error: {error_message}."
        return "rejected", reason

    if not matched_name and not accepted_name:
        return "rejected", "Rejected because GBIF returned no usable match."

    # Taxonomic-domain guard: keep the plant table to the plant kingdom. GBIF can
    # return a taxonomically correct but non-plant match for a bare name (e.g.
    # the mushrooms Ganoderma lucidum / Volvariella volvacea resolve to kingdom
    # Fungi, key 5). Reject any match whose resolved kingdom key is present and
    # is not Plantae. An empty kingdom key means GBIF gave no kingdom node, so we
    # do not penalize it here and let the normal match rules decide.
    kingdom_key = normalize_text(row.get("gbif_kingdom_key", ""))
    if kingdom_key and kingdom_key != PLANTAE_KINGDOM_KEY:
        return (
            "rejected",
            f"Rejected because GBIF resolved this name to kingdom key '{kingdom_key}', "
            f"which is not Plantae (expected '{PLANTAE_KINGDOM_KEY}'); non-plant taxa "
            "are excluded from the plant table.",
        )

    if (
        match_type in ACCEPTED_MATCH_TYPES
        and confidence is not None
        and confidence >= ACCEPT_CONFIDENCE_THRESHOLD
    ):
        if taxonomic_status in ACCEPTED_TAXONOMIC_STATUSES or not taxonomic_status:
            return (
                "accepted",
                f"Accepted because match_type='{match_type}' and confidence={confidence:g} met the acceptance threshold.",
            )
        return (
            "review",
            f"Needs review because match_type='{match_type}' and confidence={confidence:g}, but taxonomic_status='{taxonomic_status}' requires manual confirmation.",
        )

    if (
        match_type in REVIEW_MATCH_TYPES
        and confidence is not None
        and confidence >= REVIEW_CONFIDENCE_THRESHOLD
    ):
        return (
            "review",
            f"Needs review because match_type='{match_type}' with confidence={confidence:g} is plausible but not strong enough for automatic acceptance.",
        )

    if match_type in {"HIGHERRANK", "HIGHER_RANK"}:
        if confidence is not None and confidence >= HIGHERRANK_REVIEW_THRESHOLD:
            return (
                "review",
                f"Needs review because match_type='{match_type}' is above species level with confidence={confidence:g}.",
            )
        return (
            "rejected",
            f"Rejected because match_type='{match_type}' is above species level and confidence={confidence if confidence is not None else 'missing'}.",
        )

    if not match_type:
        return "review", "Needs review because GBIF match_type is missing."

    return (
        "rejected",
        f"Rejected because match_type='{match_type}' and confidence={confidence if confidence is not None else 'missing'} did not meet acceptance or review thresholds.",
    )


def choose_canonical_scientific_name(row: pd.Series) -> str:
    """
    canonical_scientific_name should be the accepted cleaned plant name, not source text.
    Prefer GBIF accepted_name, then matched_name only if needed.
    """
    accepted_name = normalize_text(row.get("accepted_name", ""))
    matched_name = normalize_text(row.get("matched_name", ""))
    if accepted_name:
        return accepted_name
    return matched_name


def coerce_source_name(row: pd.Series, fallback_source_name: str) -> str:
    existing = normalize_text(row.get("source_name", ""))
    return existing if existing else fallback_source_name


def enrich_row(row: pd.Series, source_name: str) -> Dict[str, Any]:
    enriched = row.to_dict()

    # Correct schema fields.
    enriched["source_name"] = coerce_source_name(row, source_name)
    enriched["canonical_scientific_name"] = choose_canonical_scientific_name(row)
    enriched["authorship"] = normalize_text(row.get("authorship", ""))

    # Normalize GBIF identifier fields so they never become float-like strings.
    for field in GBIF_ID_FIELDS:
        if field in enriched:
            enriched[field] = normalize_id_like(enriched.get(field, ""))

    # Normalize a few common match metadata fields.
    for field in [
        "gbif_usage_key",
        "gbif_accepted_usage_key",
        "gbif_species_key",
        "gbif_genus_key",
        "gbif_family_key",
        "gbif_kingdom_key",
        "cache_key",
        "cache_path",
        "input_name",
        "raw_plant_id",
        "canonical_lookup_key",
        "matched_name",
        "accepted_name",
        "rank",
        "taxonomic_status",
        "match_type",
        "query_status",
        "error_message",
    ]:
        if field in enriched:
            enriched[field] = normalize_text(enriched.get(field, ""))

    decision, reason = determine_decision(row)
    enriched["decision"] = decision
    enriched["decision_reason"] = reason

    return enriched


def build_output_columns(df: pd.DataFrame) -> List[str]:
    """
    Preserve all original columns and append canonical fields at the front.
    """
    preferred_front = [
        "decision",
        "decision_reason",
        "source_name",
        "canonical_scientific_name",
        "authorship",
    ]
    existing_front = [c for c in preferred_front if c in df.columns]
    remaining = [c for c in df.columns if c not in existing_front]
    return existing_front + remaining


def classify_rows(df: pd.DataFrame, source_name: str) -> pd.DataFrame:
    enriched_records = [enrich_row(row, source_name) for _, row in df.iterrows()]
    out_df = pd.DataFrame(enriched_records)

    # Ensure consistent ordering and stable strings.
    out_df = out_df.copy()
    for col in out_df.columns:
        if out_df[col].dtype != object:
            out_df[col] = out_df[col].astype(str)

    out_df = out_df[build_output_columns(out_df)]
    return out_df


def split_outputs(df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    accepted_df = df.loc[df["decision"] == "accepted"].copy()
    review_df = df.loc[df["decision"] == "review"].copy()
    rejected_df = df.loc[df["decision"] == "rejected"].copy()
    return accepted_df, review_df, rejected_df


def write_csv(df: pd.DataFrame, path: Path) -> None:
    ensure_dir(path.parent)
    df.to_csv(path, index=False, encoding="utf-8")


def write_report(
    result: BuildCanonicalResult,
    counts: Dict[str, int],
    review_rows: pd.DataFrame,
    report_path: Path,
) -> None:
    lines = [
        "04_BUILD_CANONICAL (PART 1) REPORT",
        "=================================",
        f"input_rows={result.input_rows}",
        f"accepted_rows={result.accepted_rows}",
        f"review_rows={result.review_rows}",
        f"rejected_rows={result.rejected_rows}",
        "",
        "Decision counts:",
        f"accepted={counts.get('accepted', 0)}",
        f"review={counts.get('review', 0)}",
        f"rejected={counts.get('rejected', 0)}",
        "",
        "Rules:",
        f"- accepted: match_type in {sorted(ACCEPTED_MATCH_TYPES)} and confidence >= {ACCEPT_CONFIDENCE_THRESHOLD:g} and taxonomic_status in {sorted(ACCEPTED_TAXONOMIC_STATUSES)}",
        "- review: plausible but not strong enough for automatic acceptance, or higher-rank match needing manual confirmation",
        "- rejected: failed query, missing usable match, or weak/ambiguous match",
        "",
        "Schema corrections applied:",
        "- source_name is treated as the source system name, not the plant name",
        "- canonical_scientific_name is populated from GBIF accepted_name when available",
        "- authorship is stored separately",
        "- GBIF identifier fields are normalized to plain string form",
        "",
        f"accepted_path={result.accepted_path}",
        f"review_path={result.review_path}",
        f"rejected_path={result.rejected_path}",
        f"report_path={report_path}",
        "status=success",
    ]

    if result.review_rows > 0:
        lines.extend(
            ["", "Manual review results (input_name, matched_name, ACCEPTED/REJECTED):"]
        )
        for i, row in enumerate(review_rows.itertuples(index=False), start=1):
            lines.append(f"{i}. {row.input_name}, {row.matched_name}, UNREVIEWED")

    report_path.write_text("\n".join(lines), encoding="utf-8")


def build_canonical(
    input_path: Path,
    output_dir: Path,
    accepted_file: str,
    review_file: str,
    rejected_file: str,
    manually_accepted_review_file: str,
    report_file: str,
    source_name: str,
) -> BuildCanonicalResult:
    logging.info("Reading GBIF match output: %s", input_path)
    df = load_input(input_path)

    if df.empty:
        logging.warning("Input file is empty; writing empty outputs.")

    classified_df = classify_rows(df, source_name=source_name)
    accepted_df, review_df, rejected_df = split_outputs(classified_df)

    ensure_dir(output_dir)
    accepted_path = output_dir / accepted_file
    review_path = output_dir / review_file
    rejected_path = output_dir / rejected_file
    manually_accepted_review_path = output_dir / manually_accepted_review_file
    report_path = output_dir / report_file

    logging.info("Writing accepted rows: %s", accepted_path)
    write_csv(accepted_df, accepted_path)

    logging.info("Writing review rows: %s", review_path)
    write_csv(review_df, review_path)

    logging.info("Writing rejected rows: %s", rejected_path)
    write_csv(rejected_df, rejected_path)

    # Seed the manual-review file WITHOUT destroying curator work. This file is
    # populated by the resolve_manual_reviews stage (from manual_review_decisions.csv)
    # and consumed by part 2. A blind overwrite here silently wiped 24 human-verified
    # species on every rerun, so only write the empty header stub when no populated
    # file already exists.
    preserve_existing = False
    if manually_accepted_review_path.exists():
        try:
            existing = pd.read_csv(
                manually_accepted_review_path,
                dtype=str,
                keep_default_na=False,
                na_filter=False,
            )
        except Exception:
            existing = pd.DataFrame()
        preserve_existing = not existing.empty

    if preserve_existing:
        logging.warning(
            "Preserving existing populated manual-review file (%d rows), not overwriting: %s",
            len(existing),
            manually_accepted_review_path,
        )
    else:
        logging.info(
            "Writing empty manually accepted review file: %s",
            manually_accepted_review_path,
        )
        review_df.head(0).to_csv(manually_accepted_review_path, index=False)

    result = BuildCanonicalResult(
        input_rows=len(classified_df),
        accepted_rows=len(accepted_df),
        review_rows=len(review_df),
        rejected_rows=len(rejected_df),
        output_dir=output_dir,
        accepted_path=accepted_path,
        review_path=review_path,
        rejected_path=rejected_path,
        report_path=report_path,
        log_path=Path(),
    )

    counts = {
        "accepted": result.accepted_rows,
        "review": result.review_rows,
        "rejected": result.rejected_rows,
    }
    write_report(result, counts, review_df, report_path)
    return result


def main() -> int:
    args = parse_args()
    cfg = load_settings("plants")
    ensure_dir(args.output_dir)
    log = shared_setup_logging("plants.04_build_canonical_part1", cfg)

    log.info("Starting 04_build_canonical part 1")
    log.info("Log file: %s", args.output_dir / args.log_file)

    try:
        result = build_canonical(
            input_path=args.input,
            output_dir=args.output_dir,
            accepted_file=args.accepted_file,
            review_file=args.review_file,
            rejected_file=args.rejected_file,
            manually_accepted_review_file=args.manually_accepted_review_file,
            report_file=args.report_file,
            source_name=args.source_name,
        )
        log.info(
            "Done. input_rows=%d accepted_rows=%d review_rows=%d rejected_rows=%d",
            result.input_rows,
            result.accepted_rows,
            result.review_rows,
            result.rejected_rows,
        )
        return 0
    except Exception as exc:
        logging.exception("Canonical classification failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
