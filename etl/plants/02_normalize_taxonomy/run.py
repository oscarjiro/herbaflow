"""
02_normalize_taxonomy: normalize plant scientific-name strings before GBIF matching.

Input:
    01_extract/out/stg_plants.csv

Output:
    02_normalize_taxonomy/out/normalized_plants.csv
    02_normalize_taxonomy/out/normalize_taxonomy_report.txt

This step:
- preserves source metadata and raw plant rows
- trims excessive whitespace
- keeps the original scraped species name in a separate column
- splits scientific-name strings into:
    * verbatim_scientific_name
    * canonical_candidate_name
    * authorship_candidate
- builds canonical_lookup_key from normalized plant name text
- does not call GBIF
- only drops rows that are truly invalid (missing any usable plant-name text)

Run:
    python normalize_taxonomy.py \
        --input 01_extract/out/stg_plants.csv \
        --output-dir 02_normalize_taxonomy/out
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
import argparse
import logging
import re
import unicodedata
from dataclasses import dataclass
from typing import List, Tuple

import pandas as pd
from shared.utils import ETL_ROOT, ensure_dir, load_settings
from shared.utils import setup_logging as shared_setup_logging


def _defaults() -> tuple[Path, Path, str, str, str]:
    cfg = load_settings("plants")
    step = cfg["paths"]["normalize_taxonomy"]
    return (
        ETL_ROOT / step["input"],
        ETL_ROOT / step["output_dir"],
        step["output_file"],
        step["report_file"],
        step["log_file"],
    )

REQUIRED_NAME_COLUMN = "species_name"

RANK_MARKERS = {
    "subsp.",
    "subsp",
    "ssp.",
    "ssp",
    "var.",
    "var",
    "f.",
    "f",
    "fo.",
    "fo",
    "forma",
    "subvar.",
    "subvar",
    "sect.",
    "sect",
    "series",
    "ser.",
    "ser",
    "nothosubsp.",
    "nothosubsp",
    "nothovar.",
    "nothovar",
}

WHITESPACE_RE = re.compile(r"\s+")
TRAILING_PUNCT_RE = re.compile(r"[,\.;:]+$")


@dataclass(frozen=True)
class NormalizeResult:
    input_rows: int
    output_rows: int
    invalid_rows_removed: int
    names_changed: int
    rows_with_authorship_extracted: int
    rows_with_whitespace_trimmed: int
    output_path: Path
    report_path: Path
    log_path: Path


def parse_args() -> argparse.Namespace:
    default_input, default_output_dir, default_output_file, default_report_file, default_log_file = _defaults()
    parser = argparse.ArgumentParser(
        description="Normalize plant scientific-name strings before GBIF matching."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=default_input,
        help="Path to staged input CSV (default: plants/01_extract/out/stg_plants.csv)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=default_output_dir,
        help="Directory where normalized outputs will be written (default: plants/02_normalize_taxonomy/out)",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default=default_output_file,
        help="Name of normalized output CSV (default: normalized_plants.csv)",
    )
    parser.add_argument(
        "--report-file",
        type=str,
        default=default_report_file,
        help="Name of normalization report text file (default: normalize_taxonomy_report.txt)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=default_log_file,
        help="Name of log file (default: normalize_taxonomy.log)",
    )
    return parser.parse_args()



def load_input(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    df = pd.read_csv(input_path, dtype=str, keep_default_na=False, na_filter=False)
    if REQUIRED_NAME_COLUMN not in df.columns:
        raise ValueError(
            f"Required column '{REQUIRED_NAME_COLUMN}' not found in {input_path}"
        )
    return df


def normalize_whitespace(value: str) -> str:
    if value is None:
        return ""
    value = unicodedata.normalize("NFKC", str(value))
    value = value.replace("\u00a0", " ")  # non-breaking space
    value = value.replace("\u200b", "")  # zero-width space
    value = WHITESPACE_RE.sub(" ", value)
    return value.strip()


def clean_token(token: str) -> str:
    token = normalize_whitespace(token)
    token = token.strip()
    return token


def normalize_scientific_string(value: str) -> str:
    """
    Light normalization before GBIF matching:
    - trims outer whitespace
    - collapses repeated whitespace
    - normalizes Unicode compatibility forms
    - preserves the original textual content as much as possible
    """
    value = normalize_whitespace(value)
    # Normalize common punctuation spacing only.
    value = re.sub(r"\s*\(\s*", " (", value)
    value = re.sub(r"\s*\)\s*", ") ", value)
    value = re.sub(r"\s*,\s*", ", ", value)
    value = re.sub(r"\s*;\s*", "; ", value)
    value = re.sub(r"\s+\.", ".", value)
    value = WHITESPACE_RE.sub(" ", value).strip()
    return value


def split_scientific_name(scientific_name: str) -> Tuple[str, str, str]:
    """
    Split a scientific name string into:
      - verbatim_scientific_name
      - canonical_candidate_name
      - authorship_candidate

    Heuristic only; no GBIF lookup is performed here.
    """
    verbatim = normalize_scientific_string(scientific_name)
    if not verbatim:
        return "", "", ""

    tokens = verbatim.split(" ")
    if len(tokens) == 1:
        return verbatim, verbatim, ""

    # Start with genus + specific epithet if present.
    canonical_tokens: List[str] = [tokens[0]]
    index = 1

    if len(tokens) >= 2:
        canonical_tokens.append(tokens[1])
        index = 2

    # Extend canonical candidate for simple infraspecific ranks / hybrid forms.
    while index < len(tokens):
        token = tokens[index]
        low = token.lower().strip()
        if low in RANK_MARKERS:
            canonical_tokens.append(token)
            index += 1
            if index < len(tokens):
                canonical_tokens.append(tokens[index])
                index += 1
            continue

        if token in {"×", "x"}:
            canonical_tokens.append(token)
            index += 1
            if index < len(tokens):
                canonical_tokens.append(tokens[index])
                index += 1
            continue

        break

    canonical_candidate = normalize_whitespace(" ".join(canonical_tokens))
    remaining_tokens = tokens[len(canonical_tokens) :]
    authorship_candidate = normalize_whitespace(" ".join(remaining_tokens))

    # If the remainder is just a trailing author abbreviation, keep it as authorship.
    # If the heuristic mis-classified too much into authorship, preserve it anyway.
    return verbatim, canonical_candidate, authorship_candidate


def canonical_lookup_key(value: str) -> str:
    """
    Build a lookup key from normalized plant name text.
    Lowercased, accent-folded, punctuation-stripped, whitespace-collapsed.
    """
    value = normalize_scientific_string(value)
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s]+", " ", value)
    value = WHITESPACE_RE.sub(" ", value).strip()
    return value


def normalize_dataframe(df: pd.DataFrame) -> Tuple[pd.DataFrame, NormalizeResult]:
    input_rows = len(df)

    # Preserve the raw scraped name in a dedicated column.
    df = df.copy()
    df["original_species_name"] = df[REQUIRED_NAME_COLUMN].astype(str)

    # Determine invalid rows before normalization.
    original_trimmed = df["original_species_name"].map(normalize_whitespace)
    invalid_mask = original_trimmed.eq("")
    invalid_rows_removed = int(invalid_mask.sum())

    if invalid_rows_removed:
        logging.warning(
            "Found %d invalid rows with empty species_name; these will be dropped.",
            invalid_rows_removed,
        )

    df = df.loc[~invalid_mask].copy()

    # Normalize preserved fields lightly.
    fields_to_preserve = [
        "family_name",
        "common_name",
        "classification",
        "purpose",
        "reference",
        "detail_url",
    ]
    for field in fields_to_preserve:
        if field in df.columns:
            df[field] = df[field].map(normalize_whitespace)

    if "source_batch_id" in df.columns:
        df["source_batch_id"] = df["source_batch_id"].map(normalize_whitespace)
    if "raw_hash" in df.columns:
        df["raw_hash"] = df["raw_hash"].map(normalize_whitespace)

    # Split scientific name text.
    splits = df["original_species_name"].map(split_scientific_name)
    df["verbatim_scientific_name"] = splits.map(lambda t: t[0])
    df["canonical_candidate_name"] = splits.map(lambda t: t[1])
    df["authorship_candidate"] = splits.map(lambda t: t[2])

    # The lookup key is based on the canonical candidate.
    df["canonical_lookup_key"] = df["canonical_candidate_name"].map(
        canonical_lookup_key
    )

    # Count change metrics.
    trimmed_changed = int(
        (
            original_trimmed != df["original_species_name"].map(normalize_whitespace)
        ).sum()
    )
    names_changed = int(
        (
            df["original_species_name"].map(normalize_whitespace)
            != df["verbatim_scientific_name"]
        ).sum()
    )
    rows_with_authorship_extracted = int(df["authorship_candidate"].ne("").sum())

    # Determine rows where whitespace normalization changed the visible text.
    rows_with_whitespace_trimmed = int(
        (
            df["original_species_name"]
            != df["original_species_name"].map(normalize_whitespace)
        ).sum()
    )

    output_rows = len(df)

    result = NormalizeResult(
        input_rows=input_rows,
        output_rows=output_rows,
        invalid_rows_removed=invalid_rows_removed,
        names_changed=names_changed,
        rows_with_authorship_extracted=rows_with_authorship_extracted,
        rows_with_whitespace_trimmed=rows_with_whitespace_trimmed,
        output_path=Path(),
        report_path=Path(),
        log_path=Path(),
    )
    return df, result


def enforce_column_order(df: pd.DataFrame) -> pd.DataFrame:
    """
    Keep source metadata intact, then append normalized fields at the end.
    """
    preferred_first = [
        "plant_id",
        "original_species_name",
        "verbatim_scientific_name",
        "canonical_candidate_name",
        "authorship_candidate",
        "canonical_lookup_key",
        "family_name",
        "common_name",
        "classification",
        "purpose",
        "reference",
        "detail_url",
        "source_batch_id",
        "raw_hash",
    ]

    existing = [col for col in preferred_first if col in df.columns]
    remaining = [col for col in df.columns if col not in existing]
    return df[existing + remaining]


def write_report(result: NormalizeResult, output_path: Path, report_path: Path) -> None:
    lines = [
        "02_NORMALIZE_TAXONOMY REPORT",
        "============================",
        f"input_rows={result.input_rows}",
        f"output_rows={result.output_rows}",
        f"invalid_rows_removed={result.invalid_rows_removed}",
        f"names_changed={result.names_changed}",
        f"rows_with_authorship_extracted={result.rows_with_authorship_extracted}",
        f"rows_with_whitespace_trimmed={result.rows_with_whitespace_trimmed}",
        f"output_path={output_path}",
        f"report_path={report_path}",
        "status=success",
        "",
        "Notes:",
        "- No GBIF lookup was performed in this step.",
        "- Original scraped names are preserved in original_species_name.",
        "- canonical_candidate_name is a heuristic pre-GBIF candidate.",
    ]
    report_path.write_text("\n".join(lines), encoding="utf-8")


def normalize_taxonomy(
    input_path: Path,
    output_dir: Path,
    output_file: str,
    report_file: str,
) -> NormalizeResult:
    logging.info("Reading staged input: %s", input_path)
    df = load_input(input_path)

    normalized_df, result = normalize_dataframe(df)
    normalized_df = enforce_column_order(normalized_df)

    ensure_dir(output_dir)
    output_path = output_dir / output_file
    report_path = output_dir / report_file

    logging.info("Writing normalized CSV: %s", output_path)
    normalized_df.to_csv(output_path, index=False, encoding="utf-8")

    logging.info("Writing normalization report: %s", report_path)
    write_report(result, output_path, report_path)

    return NormalizeResult(
        input_rows=result.input_rows,
        output_rows=result.output_rows,
        invalid_rows_removed=result.invalid_rows_removed,
        names_changed=result.names_changed,
        rows_with_authorship_extracted=result.rows_with_authorship_extracted,
        rows_with_whitespace_trimmed=result.rows_with_whitespace_trimmed,
        output_path=output_path,
        report_path=report_path,
        log_path=Path(),
    )


def main() -> int:
    args = parse_args()
    cfg = load_settings("plants")
    ensure_dir(args.output_dir)
    log = shared_setup_logging("plants.02_normalize_taxonomy", cfg)

    log.info("Starting 02_normalize_taxonomy")
    log.info("Log file: %s", args.output_dir / args.log_file)

    try:
        result = normalize_taxonomy(
            input_path=args.input,
            output_dir=args.output_dir,
            output_file=args.output_file,
            report_file=args.report_file,
        )
        log.info(
            "Normalization complete. input_rows=%d output_rows=%d invalid_rows_removed=%d names_changed=%d",
            result.input_rows,
            result.output_rows,
            result.invalid_rows_removed,
            result.names_changed,
        )
        return 0
    except Exception as exc:
        logging.exception("Normalization failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
