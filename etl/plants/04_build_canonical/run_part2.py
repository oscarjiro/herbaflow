"""
04_build_canonical (part 2): build final canonical plant seed files from accepted rows.

Input:
    04_build_canonical/out/accepted_plants.csv

Outputs:
    04_build_canonical/out/plants.csv
    04_build_canonical/out/plant_aliases.csv
    04_build_canonical/out/build_canonical_part2_report.txt
    04_build_canonical/out/build_canonical_part2.log

This script:
- creates one canonical plant row per accepted plant
- creates alias rows for exact scraped spelling, synonym variants, author variants,
  and other normalized name variants
- generates stable plant_id, alias_id, and canonical_key values
- preserves source provenance columns
- keeps retrieved_at and source_batch_id
- avoids confusing source_name with the plant name
- writes deterministic outputs suitable for Supabase/PostgreSQL import

Run:
    python build_canonical_part2.py \
        --input 04_build_canonical/out/accepted_plants.csv \
        --output-dir 04_build_canonical/out
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir
from plants.utils import plant_canonical_key, plant_id as make_plant_id, plant_alias_id as make_alias_id
from shared.identity import pick_alias
from shared.provenance import gbif_species_url

import argparse
import logging
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Dict, List, Sequence, Tuple

import pandas as pd


DEFAULT_SOURCE_NAME = "KNApSAcK World"


def _defaults() -> dict:
    cfg = load_settings("plants")
    return cfg["paths"]["build_canonical_part2"]

WHITESPACE_RE = re.compile(r"\s+")
PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)

ALIAS_TYPES = {
    "exact_scraped_spelling",
    "synonym_variant",
    "author_variant",
    "normalized_variant",
}

GBIF_ID_FIELDS = [
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
]

PLANTS_OUTPUT_COLUMNS = [
    "plant_id",
    "raw_plant_id",
    "canonical_key",
    "canonical_scientific_name",
    "authorship",
    "family_name",
    "taxonomic_status",
    "rank",
    "gbif_usage_key",
    "gbif_accepted_usage_key",
    "gbif_species_key",
    "gbif_genus_key",
    "gbif_family_key",
    "gbif_kingdom_key",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
    "confidence",
]

ALIASES_OUTPUT_COLUMNS = [
    "alias_id",
    "plant_id",
    "alias_name",
    "alias_key",
    "alias_type",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
]


@dataclass(frozen=True)
class BuildSeedResult:
    input_rows: int
    plant_rows: int
    alias_rows: int
    group_count: int
    output_dir: Path
    plants_path: Path
    aliases_path: Path
    report_path: Path
    log_path: Path


def parse_args() -> argparse.Namespace:
    step = _defaults()
    parser = argparse.ArgumentParser(
        description="Build final canonical plant seed files from accepted GBIF rows."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=ETL_ROOT / step["input"],
        help="Path to accepted plant rows (default: plants/04_build_canonical/out/accepted_plants.csv)",
    )
    parser.add_argument(
        "--manually-accepted-review-input",
        type=Path,
        default=ETL_ROOT / step["manually_accepted_review_input"],
        help="Optional manually accepted review plants CSV to merge with accepted plants",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ETL_ROOT / step["output_dir"],
        help="Directory where final seed files will be written (default: plants/04_build_canonical/out)",
    )
    parser.add_argument(
        "--plants-file",
        type=str,
        default=step["plants_file"],
        help="Filename for canonical plants output (default: plants.csv)",
    )
    parser.add_argument(
        "--aliases-file",
        type=str,
        default=step["aliases_file"],
        help="Filename for canonical aliases output (default: plant_aliases.csv)",
    )
    parser.add_argument(
        "--report-file",
        type=str,
        default=step["report_file"],
        help="Filename for the summary report (default: build_canonical_part2_report.txt)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=step["log_file"],
        help="Filename for the log file (default: build_canonical_part2.log)",
    )
    parser.add_argument(
        "--source-name",
        type=str,
        default=DEFAULT_SOURCE_NAME,
        help='Fallback source system name (default: "KNApSAcK World")',
    )
    return parser.parse_args()



def load_input(input_path: Path) -> pd.DataFrame:
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    return pd.read_csv(input_path, dtype=str, keep_default_na=False, na_filter=False)


def load_manually_accepted_review(input_path: Path | None) -> pd.DataFrame:
    if input_path is None:
        return pd.DataFrame()

    if not input_path.exists():
        logging.warning(f"Manual review file not found: {input_path}")
        return pd.DataFrame()

    df = pd.read_csv(input_path, dtype=str, keep_default_na=False, na_filter=False)

    return df


def normalize_text(value: Any) -> str:
    if value is None:
        return ""
    text = str(value)
    text = text.replace("\u00a0", " ")
    text = text.replace("\u200b", "")
    text = unicodedata.normalize("NFKC", text)
    text = WHITESPACE_RE.sub(" ", text)
    return text.strip()


def normalize_id_like(value: Any) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    lower = text.lower()
    if lower in {"nan", "none", "null"}:
        return ""
    try:
        num = float(text)
        if math.isfinite(num) and num.is_integer():
            return str(int(num))
        return format(num, ".15g")
    except Exception:
        pass
    if re.fullmatch(r"[+-]?\d+", text):
        return str(int(text))
    return text


def fold_key_text(value: Any) -> str:
    """
    Accent-fold, lowercase, strip punctuation, and collapse whitespace.
    Suitable for stable canonical/alias keys.
    """
    text = normalize_text(value)
    if not text:
        return ""
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = text.lower()
    text = PUNCT_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    return text


def first_non_empty(*values: Any) -> str:
    for value in values:
        text = normalize_text(value)
        if text:
            return text
    return ""


def input_row_display_plant_name(row: pd.Series) -> str:
    """Human-readable source plant label for reports (not necessarily canonical)."""
    name = first_non_empty(
        row.get("input_name", ""),
        row.get("original_species_name", ""),
        row.get("verbatim_scientific_name", ""),
        row.get("canonical_candidate_name", ""),
        row.get("canonical_scientific_name", ""),
        row.get("matched_name", ""),
        row.get("accepted_name", ""),
    )
    return name if name else "(no display name)"


def coalesce_source_url(row: pd.Series) -> str:
    return first_non_empty(
        row.get("source_url", ""),
        row.get("detail_url", ""),
    )


def coalesce_retrieved_at(row: pd.Series) -> str:
    return first_non_empty(row.get("retrieved_at", ""))


def coalesce_source_name(row: pd.Series, fallback: str) -> str:
    existing = first_non_empty(row.get("source_name", ""))
    return existing if existing else fallback


def canonical_scientific_name_from_row(row: pd.Series) -> str:
    return first_non_empty(
        row.get("canonical_scientific_name", ""),
        row.get("accepted_name", ""),
        row.get("matched_name", ""),
        row.get("verbatim_scientific_name", ""),
        row.get("original_species_name", ""),
        row.get("input_name", ""),
    )


def authorship_from_row(row: pd.Series) -> str:
    return first_non_empty(
        row.get("authorship", ""),
        row.get("authorship_candidate", ""),
    )


def source_batch_id_from_row(row: pd.Series) -> str:
    return first_non_empty(row.get("source_batch_id", ""))


def confidence_value(row: pd.Series) -> str:
    return normalize_text(row.get("confidence", ""))


def clean_family_name(row: pd.Series) -> str:
    return first_non_empty(row.get("family_name", ""))


def clean_taxonomic_status(row: pd.Series) -> str:
    return first_non_empty(row.get("taxonomic_status", "")).upper()


def clean_rank(row: pd.Series) -> str:
    return first_non_empty(row.get("rank", "")).upper()


def build_canonical_key(canonical_scientific_name: str, authorship: str) -> str:
    name_key = fold_key_text(canonical_scientific_name)
    author_key = fold_key_text(authorship)
    if author_key:
        return f"{name_key}|{author_key}"
    return name_key


def build_alias_key(alias_name: str) -> str:
    return fold_key_text(alias_name)


def is_meaningful_alias(alias_name: str) -> bool:
    return bool(fold_key_text(alias_name))


def normalize_gbif_fields(row: pd.Series) -> Dict[str, str]:
    out: Dict[str, str] = {}
    for field in GBIF_ID_FIELDS:
        out[field] = normalize_id_like(row.get(field, ""))
    return out


def pick_representative_row(group: pd.DataFrame) -> pd.Series:
    """
    Deterministic representative row:
    higher confidence first, then lexicographic canonical name, then input strings.
    """
    work = group.copy()
    work["_confidence_num"] = pd.to_numeric(
        work.get("confidence", ""), errors="coerce"
    ).fillna(-1.0)
    sort_cols = ["_confidence_num"]
    ascending = [False]

    for col in [
        "canonical_scientific_name",
        "accepted_name",
        "matched_name",
        "original_species_name",
        "verbatim_scientific_name",
        "input_name",
    ]:
        if col in work.columns:
            sort_cols.append(col)
            ascending.append(True)

    work = work.sort_values(by=sort_cols, ascending=ascending, kind="stable")
    rep = work.iloc[0].drop(labels=["_confidence_num"])
    return rep


def canonicalize_group(
    group: pd.DataFrame, source_name_fallback: str
) -> Tuple[Dict[str, Any], List[Dict[str, Any]]]:
    rep = pick_representative_row(group)

    canonical_name = canonical_scientific_name_from_row(rep)
    authorship = authorship_from_row(rep)
    name_slug_source = f"{canonical_name} {authorship}".strip()
    gbif_key = (
        normalize_id_like(rep.get("gbif_accepted_usage_key", ""))
        or normalize_id_like(rep.get("gbif_usage_key", ""))
    )
    canonical_key = plant_canonical_key(gbif_key, name_slug_source)
    plant_id = make_plant_id(gbif_key, name_slug_source)

    source_name = coalesce_source_name(rep, source_name_fallback)
    source_url = gbif_species_url(gbif_key) or coalesce_source_url(rep)
    source_batch_id = source_batch_id_from_row(rep)
    retrieved_at = coalesce_retrieved_at(rep)
    confidence = confidence_value(rep)

    plant_row: Dict[str, Any] = {
        "plant_id": plant_id,
        "raw_plant_id": normalize_text(rep.get("raw_plant_id", "")),
        "canonical_key": canonical_key,
        "canonical_scientific_name": canonical_name,
        "authorship": authorship,
        "family_name": clean_family_name(rep),
        "taxonomic_status": clean_taxonomic_status(rep),
        "rank": clean_rank(rep),
        "source_name": source_name,
        "source_url": source_url,
        "source_batch_id": source_batch_id,
        "retrieved_at": retrieved_at,
        "confidence": confidence,
    }
    plant_row.update(normalize_gbif_fields(rep))

    # Collapse aliases to exactly one row per (plant_id, alias_key). The new
    # alias_id = make_alias_id(plant_id, alias_key) intentionally excludes
    # alias_type, so two candidates that fold to the same slug but carry
    # different alias_types must merge into a single deterministic row to
    # satisfy UNIQUE(plant_id, alias_key). pick_alias keeps the higher-priority
    # alias_type; plant alias types are absent from ALIAS_PRIORITY, so it is
    # first-wins (ties keep the current row) — matching the add order below.
    alias_by_key: Dict[str, Dict[str, Any]] = {}

    def add_alias(alias_name: str, alias_type: str, row_source: pd.Series) -> None:
        alias_name = normalize_text(alias_name)
        if alias_type not in ALIAS_TYPES:
            raise ValueError(f"Unsupported alias_type: {alias_type}")
        if not is_meaningful_alias(alias_name):
            return
        alias_key = build_alias_key(alias_name)
        candidate = {
            "alias_id": make_alias_id(plant_id, alias_key),
            "plant_id": plant_id,
            "alias_name": alias_name,
            "alias_key": alias_key,
            "alias_type": alias_type,
            "source_name": coalesce_source_name(row_source, source_name_fallback),
            "source_url": coalesce_source_url(row_source),
            "source_batch_id": source_batch_id_from_row(row_source),
            "retrieved_at": coalesce_retrieved_at(row_source),
        }
        alias_by_key[alias_key] = pick_alias(alias_by_key.get(alias_key), candidate)

    for _, row in group.iterrows():
        original_name = first_non_empty(
            row.get("original_species_name", ""),
            row.get("verbatim_scientific_name", ""),
        )
        canonical_candidate = first_non_empty(row.get("canonical_candidate_name", ""))
        authorship_candidate = first_non_empty(row.get("authorship_candidate", ""))
        matched_name = first_non_empty(row.get("matched_name", ""))
        accepted_name = first_non_empty(row.get("accepted_name", ""))

        # Exact scraped spelling.
        add_alias(original_name, "exact_scraped_spelling", row)

        # Other normalized variants.
        if canonical_candidate and fold_key_text(canonical_candidate) != fold_key_text(
            original_name
        ):
            add_alias(canonical_candidate, "normalized_variant", row)

        # Author variants: canonical name plus authorship candidate when available.
        if canonical_candidate and authorship_candidate:
            author_variant = f"{canonical_candidate} {authorship_candidate}".strip()
            if fold_key_text(author_variant) != fold_key_text(original_name):
                add_alias(author_variant, "author_variant", row)

        # Synonym variants: GBIF matched name when it differs from the accepted canonical name.
        if matched_name and fold_key_text(matched_name) != fold_key_text(
            canonical_name
        ):
            add_alias(matched_name, "synonym_variant", row)

        # Accepted name variant can also help preserve a normalized alias when the
        # accepted name differs from the original input spelling.
        if accepted_name and fold_key_text(accepted_name) != fold_key_text(
            original_name
        ):
            # Keep this under normalized_variant rather than inventing a new alias_type.
            add_alias(accepted_name, "normalized_variant", row)

    # One row per (plant_id, alias_key); stable, deterministic ordering.
    aliases = sorted(
        alias_by_key.values(),
        key=lambda r: (r["plant_id"], r["alias_type"], r["alias_key"], r["alias_name"]),
    )

    return plant_row, aliases


def build_seed_files(
    input_path: Path,
    manually_accepted_review_path: Path,
    output_dir: Path,
    plants_file: str,
    aliases_file: str,
    report_file: str,
    source_name_fallback: str,
) -> BuildSeedResult:
    logging.info("Reading accepted rows: %s", input_path)
    df = load_input(input_path)

    if df.empty:
        logging.warning("Accepted input is empty; output files will also be empty.")

    manually_accepted_review_df = load_manually_accepted_review(
        manually_accepted_review_path
    )

    if not manually_accepted_review_df.empty:
        logging.info(
            "Merging manually accepted review plants: %d rows",
            len(manually_accepted_review_df),
        )

        common_cols = [
            c for c in manually_accepted_review_df.columns if c in df.columns
        ]
        manually_accepted_review_df = manually_accepted_review_df[common_cols]

        df = pd.concat([df, manually_accepted_review_df], ignore_index=True)

        df = df.drop_duplicates()

    # Ensure deterministic ordering of groups.
    if "canonical_scientific_name" not in df.columns:
        raise ValueError("Input is missing required column: canonical_scientific_name")

    work = df.copy()
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
    work = work.sort_values(
        by=["__canonical_key_preview", "canonical_scientific_name", "authorship"],
        kind="stable",
    ).reset_index(drop=True)

    plant_rows: List[Dict[str, Any]] = []
    alias_rows: List[Dict[str, Any]] = []
    merged_input_notes: List[Tuple[str, str, str]] = []

    grouped = work.groupby("__canonical_key_preview", sort=True, dropna=False)
    for _, group in grouped:
        if len(group) > 1:
            rep = pick_representative_row(group)
            rep_name = canonical_scientific_name_from_row(rep)
            rep_raw = normalize_text(rep.get("raw_plant_id", ""))
            rep_summary = f"{rep_name} | raw_plant_id={rep_raw}"
            rep_idx = rep.name
            for idx, row in group.iterrows():
                if idx != rep_idx:
                    merged_input_notes.append(
                        (
                            rep_summary,
                            normalize_text(row.get("raw_plant_id", "")),
                            input_row_display_plant_name(row),
                        )
                    )

        plant_row, aliases = canonicalize_group(group, source_name_fallback)
        plant_rows.append(plant_row)
        alias_rows.extend(aliases)

    plants_df = pd.DataFrame(plant_rows)
    aliases_df = pd.DataFrame(alias_rows)

    # Stable sort for deterministic exports.
    if not plants_df.empty:
        plants_df = plants_df.sort_values(
            by=["canonical_key", "plant_id"],
            kind="stable",
        ).reset_index(drop=True)

    if not aliases_df.empty:
        aliases_df = aliases_df.sort_values(
            by=["plant_id", "alias_type", "alias_key", "alias_name"],
            kind="stable",
        ).reset_index(drop=True)

    # Ensure all required columns exist.
    for col in PLANTS_OUTPUT_COLUMNS:
        if col not in plants_df.columns:
            plants_df[col] = ""
    for col in ALIASES_OUTPUT_COLUMNS:
        if col not in aliases_df.columns:
            aliases_df[col] = ""

    # Keep any additional provenance columns from the representative plant row.
    # This makes the file more useful for auditing while remaining importable.
    extra_plant_cols = [c for c in plants_df.columns if c not in PLANTS_OUTPUT_COLUMNS]
    extra_alias_cols = [
        c for c in aliases_df.columns if c not in ALIASES_OUTPUT_COLUMNS
    ]

    plants_df = plants_df[PLANTS_OUTPUT_COLUMNS + extra_plant_cols]
    aliases_df = aliases_df[ALIASES_OUTPUT_COLUMNS + extra_alias_cols]

    ensure_dir(output_dir)
    plants_path = output_dir / plants_file
    aliases_path = output_dir / aliases_file
    report_path = output_dir / report_file

    logging.info("Writing plants seed file: %s", plants_path)
    plants_df.to_csv(plants_path, index=False, encoding="utf-8")

    logging.info("Writing alias seed file: %s", aliases_path)
    aliases_df.to_csv(aliases_path, index=False, encoding="utf-8")

    report_lines = [
        "04_BUILD_CANONICAL (PART 2) REPORT",
        "=================================",
        f"input_rows={len(df)}",
        f"group_count={len(plant_rows)}",
        f"plant_rows={len(plants_df)}",
        f"alias_rows={len(aliases_df)}",
        "",
        "Alias types used:",
        ", ".join(sorted(ALIAS_TYPES)),
        "",
        "Notes:",
        "- plant_id is a stable hash derived from canonical_key",
        "- alias_id is a stable hash derived from plant_id and alias_key",
        "- source_name is treated as the source system name, not the plant name",
        "- alias_name preserves the exact original scraped spelling where available",
        "- GBIF identifier fields are normalized to plain string form",
        "",
        f"input_rows_merged_into_shared_plant={len(merged_input_notes)}",
        "  (Each line below is an input row that did not add a plants.csv row because it",
        "   shares the same canonical group as the representative row on the right.)",
        "",
    ]

    if merged_input_notes:
        merged_input_notes.sort(key=lambda t: (t[0], t[1], t[2]))
        report_lines.append("Merged input rows (omitted from plants.csv row count):")
        for rep_summary, omitted_raw, omitted_name in merged_input_notes:
            report_lines.append(
                f"  - raw_plant_id={omitted_raw} | plant_name={omitted_name}"
                f"  ->  group (representative): {rep_summary}"
            )
    else:
        report_lines.append(
            "Merged input rows: none (every canonical group had exactly one input row)."
        )

    report_lines.extend(
        [
        "",
        f"plants_path={plants_path}",
        f"aliases_path={aliases_path}",
        f"report_path={report_path}",
        "status=success",
        "",
        "Plant columns written:",
        ", ".join(list(plants_df.columns)),
        "",
        "Alias columns written:",
        ", ".join(list(aliases_df.columns)),
        ]
    )
    report_path.write_text("\n".join(report_lines), encoding="utf-8")

    return BuildSeedResult(
        input_rows=len(df),
        plant_rows=len(plants_df),
        alias_rows=len(aliases_df),
        group_count=len(plant_rows),
        output_dir=output_dir,
        plants_path=plants_path,
        aliases_path=aliases_path,
        report_path=report_path,
        log_path=Path(),
    )


def main() -> int:
    args = parse_args()
    cfg = load_settings("plants")
    ensure_dir(args.output_dir)
    log = shared_setup_logging("plants.04_build_canonical_part2", cfg)

    log.info("Starting 04_build_canonical part 2")
    log.info("Log file: %s", args.output_dir / args.log_file)

    try:
        result = build_seed_files(
            input_path=args.input,
            manually_accepted_review_path=args.manually_accepted_review_input,
            output_dir=args.output_dir,
            plants_file=args.plants_file,
            aliases_file=args.aliases_file,
            report_file=args.report_file,
            source_name_fallback=args.source_name,
        )
        log.info(
            "Done. input_rows=%d plant_rows=%d alias_rows=%d group_count=%d",
            result.input_rows,
            result.plant_rows,
            result.alias_rows,
            result.group_count,
        )
        return 0
    except Exception as exc:
        logging.exception("Seed build failed: %s", exc)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
