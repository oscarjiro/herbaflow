"""Canonical disease build step for the refactored disease ETL pipeline.

Purpose
-------
Convert the ontology-enriched disease dataset into canonical disease and alias
tables. This step prepares PostgreSQL/Supabase-ready outputs and a flattened
alias map for downstream disease-target ETL and app search.

Inputs
------
- diseases/settings.yml for configuration and thresholds
- The previous step output from diseases/02_map_ontology/out/ by default

Outputs
-------
- diseases.csv: one canonical row per disease_key
- disease_aliases.csv: normalized alias rows linked back to disease_id and disease_key
- disease_alias_map.csv: flattened search-friendly alias map
- disease_targets_template.csv if configured
- optional manifest and log files in diseases/03_build_canonical/out/

Behavior
--------
- Uses disease_key as the stable internal linkage key
- Builds deterministic disease_id and alias_id values
- Uses ontology label as the canonical disease_name when mapping confidence is high
- Preserves source_id, source_url, source_batch_id, retrieved_at, confidence,
  and core provenance fields
- Builds aliases from user-provided aliases, normalized alias hints, and
  ontology-provided synonyms
- Deduplicates alias_map entries so user aliases and ontology synonyms do not
  produce duplicate search rows
- Avoids aggressive remapping and keeps original disease identity visible in
  seed provenance fields
- Is idempotent and safe to rerun from the command line
"""

from __future__ import annotations

import argparse
import ast
import csv
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir, now_iso
from shared.provenance import disease_ontology_url

from diseases.utils import (
    canonical_key,
    normalize_text,
    read_frame,
    clean_str,
    write_frame,
    disease_canonical_key,
    disease_id as make_disease_id,
    disease_alias_id,
    ALIAS_PRIORITY,
)

DEFAULT_SETTINGS_PATH = ETL_ROOT / "diseases" / "settings.yml"

IGNORE_INPUT_FILES = {
    "ontology_cache.csv",
    "ontology_mapping.csv",
    "mapping_report.csv",
    "disease_alias_map.csv",
    "validation_report.csv",
    "validation_report.json",
    "issues.csv",
    "run_manifest.json",
    "run.log",
}

DISEASE_OUTPUT_COLUMNS = [
    "disease_id",
    "disease_key",
    "canonical_key",
    "disease_name",
    "disease_name_clean",
    "canonical_name_source",
    "seed_disease_name",
    "seed_disease_name_clean",
    "standardized_name",
    "ontology_id",
    "ontology_source",
    "ontology_label",
    "ontology_description",
    "ontology_synonyms",
    "source_id",
    "source_name",
    "source_url",
    "retrieved_at",
    "source_reference_clean",
    "ontology_status",
    "ontology_match_method",
    "ontology_query",
    "batch_id",
    "created_at",
]

ALIAS_OUTPUT_COLUMNS = [
    "alias_id",
    "alias_key",
    "alias_name",
    "disease_id",
    "disease_key",
    "alias_type",
    "alias_source",
    "source_id",
    "source_name",
    "source_url",
    "retrieved_at",
    "source_reference_clean",
    "batch_id",
    "created_at",
]

ALIAS_MAP_COLUMNS = [
    "alias_map_id",
    "alias",
    "alias_key",
    "disease_key",
    "disease_id",
    "type",
    "source_id",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
    "confidence",
    "created_at",
]

TARGET_TEMPLATE_COLUMNS = [
    "disease_id",
    "disease_key",
    "target_id",
    "target_key",
    "target_name",
    "relationship_type",
    "evidence_source",
    "evidence_id",
    "evidence_text",
    "confidence",
    "source_id",
    "source_batch_id",
    "retrieved_at",
    "source_reference_clean",
    "batch_id",
    "created_at",
]

def _resolve_path(base_dir: Path, raw_value: str, default_value: str) -> Path:
    """Resolve a configured path relative to the project root."""
    path = Path(raw_value or default_value)
    if not path.is_absolute():
        path = (base_dir / path).resolve()
    return path


def _resolve_paths(settings: dict[str, Any], settings_path: Path) -> tuple[Path, Path]:
    """Resolve input and output paths from settings."""
    paths = settings.get("paths", {})
    input_dir = _resolve_path(
        ETL_ROOT,
        str(paths.get("ontology_out", "diseases/02_map_ontology/out")),
        "diseases/02_map_ontology/out",
    )
    output_dir = _resolve_path(
        ETL_ROOT,
        str(paths.get("canonical_out", "diseases/03_build_canonical/out")),
        "diseases/03_build_canonical/out",
    )
    return input_dir, output_dir


def _pick_first_existing(
    columns: Iterable[str], candidates: Iterable[str]
) -> str | None:
    """Return the first matching column name from a candidate list."""
    for candidate in candidates:
        if candidate in columns:
            return candidate
    return None


def _clean_name_text(value: object) -> str:
    """Normalize disease and alias text into a stable lowercase display form."""
    text = normalize_text(value)
    return text


def _clean_reference_text(value: object) -> str:
    """Clean provenance or description text without forcing lowercase."""
    text = clean_str(value)
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    text = text.strip(" ;,|/\\")
    return text


def _split_multivalue(value: object) -> list[str]:
    """Split a semicolon-, comma-, slash-, pipe-, or newline-delimited field."""
    raw = clean_str(value)
    if not raw:
        return []

    stripped = raw.strip()

    if stripped[:1] in {"[", "(", "{"}:
        try:
            parsed = ast.literal_eval(stripped)
            if isinstance(parsed, (list, tuple, set)):
                out: list[str] = []
                for item in parsed:
                    cleaned = _clean_name_text(item)
                    if cleaned:
                        out.append(cleaned)
                if out:
                    return out
        except Exception:
            pass

    parts = re.split(r"[;|,/\n]+", stripped)
    out = []
    for part in parts:
        cleaned = _clean_name_text(part)
        if cleaned:
            out.append(cleaned)
    return out


def _safe_float(value: object, default: float = 0.0) -> float:
    """Convert a value to float safely."""
    text = clean_str(value)
    if not text:
        return default
    try:
        return float(text)
    except Exception:
        return default


def _confidence_threshold(settings: dict[str, Any]) -> float:
    """Read the confidence threshold used to trust ontology labels as canonical names."""
    ontology_cfg = settings.get("ontology", {})
    canonical_cfg = settings.get("canonical", {})

    for key in (
        "canonical_name_confidence_threshold",
        "confidence_threshold",
        "label_confidence_threshold",
    ):
        if key in ontology_cfg:
            return _safe_float(ontology_cfg.get(key), 0.8)
        if key in canonical_cfg:
            return _safe_float(canonical_cfg.get(key), 0.8)

    return 0.8


def _resolve_input_path(input_dir: Path) -> Path:
    """Resolve the primary ontology-enriched input CSV."""
    preferred_names = [
        "disease_seed.csv",
        "disease_normalized.csv",
        "disease_ontology_mapped.csv",
        "disease_mapped.csv",
        "normalized_disease.csv",
        "ontology_mapping.csv",
    ]

    for name in preferred_names:
        candidate = input_dir / name
        if candidate.exists():
            return candidate

    candidates = [
        path
        for path in sorted(input_dir.glob("*.csv"))
        if path.name not in IGNORE_INPUT_FILES
    ]

    if len(candidates) == 1:
        return candidates[0]

    if not candidates:
        raise FileNotFoundError(f"No input CSV found in {input_dir}")

    raise FileNotFoundError(
        f"Could not resolve a single ontology input CSV in {input_dir}. "
        f"Expected a preferred filename or exactly one non-auxiliary CSV."
    )


def _group_disease_key(row: pd.Series) -> str:
    """Resolve the stable disease_key for a row."""
    for col in (
        "disease_key",
        "canonical_key",
        "disease_slug",
        "standardized_key",
        "normalized_key",
    ):
        if col in row.index:
            key = canonical_key(row.get(col, ""))
            if key:
                return key

    for col in (
        "disease_name_clean",
        "standardized_name",
        "ontology_label",
        "disease_name",
        "name",
        "condition",
    ):
        if col in row.index:
            key = canonical_key(row.get(col, ""))
            if key:
                return key

    return ""


def _detect_seed_name(row: pd.Series) -> str:
    """Return the best seed/original disease name available in the row."""
    for col in (
        "seed_disease_name",
        "disease_name",
        "disease",
        "name",
        "condition",
        "raw_disease_name",
        "source_name_raw",
    ):
        if col in row.index:
            value = _clean_name_text(row.get(col, ""))
            if value:
                return value

    for col in ("disease_name_clean", "standardized_name", "ontology_label"):
        if col in row.index:
            value = _clean_name_text(row.get(col, ""))
            if value:
                return value

    return ""


def _detect_seed_name_clean(row: pd.Series) -> str:
    """Return the best cleaned seed name available in the row."""
    for col in (
        "seed_disease_name_clean",
        "disease_name_clean",
        "standardized_name",
    ):
        if col in row.index:
            value = _clean_name_text(row.get(col, ""))
            if value:
                return value

    return _clean_name_text(_detect_seed_name(row))


def _detect_ontology_synonyms(row: pd.Series) -> list[str]:
    """Collect ontology-provided synonyms from likely columns."""
    candidates: list[str] = []
    for col in (
        "ontology_synonyms",
        "ontology_aliases",
        "ontology_alt_labels",
        "synonym_clean",
        "synonyms_clean",
        "synonyms",
        "aliases",
    ):
        if col in row.index:
            candidates.extend(_split_multivalue(row.get(col, "")))
    seen: set[str] = set()
    out: list[str] = []
    for item in candidates:
        key = canonical_key(item)
        if key and key not in seen:
            seen.add(key)
            out.append(item)
    return out


def _detect_alias_sources(
    row: pd.Series, include_ontology_synonyms: bool
) -> list[tuple[str, str, str]]:
    """
    Extract alias candidates as tuples of (alias_name, alias_type, alias_source).

    The function is conservative: it only includes clearly synonym-like columns
    and, when trusted, ontology-provided synonyms.
    """
    candidates: list[tuple[str, str, str]] = []

    alias_columns = []
    for col in row.index:
        lower = col.lower()
        if any(
            token in lower for token in ("alias", "synonym", "other_name", "alt_name")
        ):
            alias_columns.append(col)

    for col in alias_columns:
        lower = col.lower()
        if "ontology" in lower and "synonym" in lower and not include_ontology_synonyms:
            continue

        alias_type = (
            "ontology_synonym"
            if "ontology" in lower
            else (
                "normalized_alias"
                if lower.endswith("_clean") or "clean" in lower
                else "user_alias"
            )
        )

        if "synonym" in lower or "alias" in lower or "other_name" in lower:
            for token in _split_multivalue(row.get(col, "")):
                cleaned = _clean_name_text(token)
                if cleaned:
                    candidates.append((cleaned, alias_type, col))

    return candidates


def _status_rank(status: str) -> int:
    """Rank ontology status values so better matches sort first."""
    value = clean_str(status).lower()
    if value == "matched":
        return 3
    if value == "ambiguous":
        return 2
    if value == "seed_provided":
        return 2
    if value == "cache":
        return 2
    if value == "unmapped":
        return 0
    return 1


def _pick_representative_row(group: pd.DataFrame) -> pd.Series:
    """Pick the best row to represent a disease_key group."""
    temp = group.copy()

    if "ontology_confidence" in temp.columns:
        temp["_confidence_score"] = temp["ontology_confidence"].map(_safe_float)
    elif "confidence" in temp.columns:
        temp["_confidence_score"] = temp["confidence"].map(_safe_float)
    else:
        temp["_confidence_score"] = 0.0

    if "ontology_status" in temp.columns:
        temp["_status_score"] = temp["ontology_status"].map(_status_rank)
    else:
        temp["_status_score"] = 0

    if "ontology_label" in temp.columns:
        temp["_label_score"] = temp["ontology_label"].map(
            lambda v: 1 if clean_str(v) else 0
        )
    else:
        temp["_label_score"] = 0

    sort_cols = ["_confidence_score", "_status_score", "_label_score"]
    temp = temp.sort_values(
        by=sort_cols, ascending=[False, False, False], kind="mergesort"
    )
    return temp.iloc[0]


def _choose_canonical_name(row: pd.Series, confident: bool) -> tuple[str, str]:
    """
    Choose the canonical disease_name and its source.

    If the ontology mapping is confident, the ontology label is used as the
    visible canonical name. Otherwise the seed/original disease name is kept.
    """
    ontology_label = _clean_name_text(row.get("ontology_label", ""))
    standardized_name = _clean_name_text(row.get("standardized_name", ""))
    seed_name = _detect_seed_name(row)

    label = ontology_label or standardized_name

    if confident and label:
        return label, "ontology_label"

    return seed_name or label, "seed_disease_name"


def _merge_alias_candidate(
    bucket: dict[str, dict[str, Any]],
    *,
    alias_name: str,
    alias_type: str,
    alias_source: str,
    disease_id: str,
    disease_key: str,
    source_id: str,
    source_name: str,
    source_url: str,
    source_batch_id: str,
    retrieved_at: str,
    confidence: float,
    source_reference_clean: str,
    batch_id: str,
) -> None:
    """Insert or update an alias candidate using a conservative priority rule."""
    alias_key = canonical_key(alias_name)
    if not alias_key or alias_key == disease_key:
        return

    current = bucket.get(alias_key)
    candidate = {
        "alias_id": disease_alias_id(disease_id, alias_key),
        "alias_key": alias_key,
        "alias_name": alias_name,
        "disease_id": disease_id,
        "disease_key": disease_key,
        "alias_type": alias_type,
        "alias_source": alias_source,
        "source_id": source_id,
        "source_name": source_name,
        "source_url": source_url,
        "source_batch_id": source_batch_id,
        "retrieved_at": retrieved_at,
        "confidence": confidence,
        "source_reference_clean": source_reference_clean,
        "batch_id": batch_id,
        "created_at": now_iso(),
        "_priority": ALIAS_PRIORITY.get(alias_type, 0),
    }

    if current is None or candidate["_priority"] > current["_priority"]:
        bucket[alias_key] = candidate


def _make_target_template(path: Path) -> None:
    """Write a header-only disease-target template."""
    ensure_dir(path.parent)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(TARGET_TEMPLATE_COLUMNS)


def run(settings_path: str | Path = DEFAULT_SETTINGS_PATH) -> dict[str, Any]:
    """Run the canonical build step and return a summary dictionary."""
    settings_path = Path(settings_path)
    settings = load_settings("diseases")
    logger = shared_setup_logging("diseases.03_build_canonical", settings)

    input_dir, output_dir = _resolve_paths(settings, settings_path)
    ensure_dir(output_dir)

    input_path = _resolve_input_path(input_dir)
    df = read_frame(input_path)

    canonical_cfg = settings.get("canonical", {})
    export_cfg = settings.get("export", {})

    confidence_threshold = _confidence_threshold(settings)
    write_targets_template = bool(
        canonical_cfg.get(
            "write_targets_template",
            export_cfg.get("write_targets_template", True),
        )
    )

    if "disease_key" not in df.columns:
        df["disease_key"] = df.apply(_group_disease_key, axis=1)
    else:
        df["disease_key"] = df["disease_key"].map(canonical_key)
        missing_keys = df["disease_key"].map(lambda v: clean_str(v) == "")
        if missing_keys.any():
            df.loc[missing_keys, "disease_key"] = df.loc[missing_keys].apply(
                _group_disease_key, axis=1
            )

    if "canonical_key" not in df.columns:
        df["canonical_key"] = df["disease_key"]

    diseases: list[dict[str, Any]] = []
    aliases: list[dict[str, Any]] = []
    alias_map_rows: list[dict[str, Any]] = []

    for disease_key, group in df.groupby("disease_key", sort=False):
        disease_key = canonical_key(disease_key)
        if not disease_key:
            continue

        rep = _pick_representative_row(group)
        confidence = _safe_float(
            rep.get("ontology_confidence", rep.get("confidence", 0.0))
        )
        ontology_status = clean_str(rep.get("ontology_status", ""))
        ontology_label = _clean_name_text(
            rep.get("ontology_label", "")
        ) or _clean_name_text(rep.get("standardized_name", ""))
        is_confident = bool(
            ontology_label
            and confidence >= confidence_threshold
            and clean_str(ontology_status).lower()
            in {"matched", "seed_provided", "cache", "ambiguous"}
        )

        disease_name, canonical_name_source = _choose_canonical_name(rep, is_confident)

        seed_name = _detect_seed_name(rep)
        seed_name_clean = _detect_seed_name_clean(rep)
        ontology_synonyms = _detect_ontology_synonyms(rep)

        ontology_source = clean_str(rep.get("ontology_source", ""))
        ontology_id = clean_str(rep.get("ontology_id", ""))
        canonical_key_value = disease_canonical_key(ontology_source, ontology_id, disease_key)
        disease_id = make_disease_id(ontology_source, ontology_id, disease_key)
        source_id = (
            clean_str(rep.get("source_id", ""))
            or clean_str(rep.get("seed_id", ""))
            or disease_key
        )
        source_name = clean_str(rep.get("source_name", "")) or clean_str(
            settings.get("source_name", "")
        )
        source_url = (
            disease_ontology_url(ontology_source, ontology_id)
            or clean_str(rep.get("source_url", ""))
            or clean_str(settings.get("source_url", ""))
        )
        source_batch_id = (
            clean_str(rep.get("source_batch_id", ""))
            or clean_str(rep.get("batch_id", ""))
            or clean_str(settings.get("batch_id", ""))
        )
        retrieved_at = clean_str(rep.get("retrieved_at", "")) or clean_str(
            settings.get("retrieved_at", "")
        )
        source_reference_clean = clean_str(
            rep.get("source_reference_clean", "")
        ) or clean_str(rep.get("source_reference", ""))
        batch_id = clean_str(rep.get("batch_id", "")) or clean_str(
            settings.get("batch_id", "")
        )

        disease_row = {
            "disease_id": disease_id,
            "disease_key": disease_key,
            "canonical_key": canonical_key_value,
            "disease_name": _clean_name_text(disease_name),
            "disease_name_clean": _clean_name_text(disease_name),
            "canonical_name_source": canonical_name_source,
            "seed_disease_name": seed_name,
            "seed_disease_name_clean": seed_name_clean,
            "standardized_name": ontology_label,
            "ontology_id": ontology_id,
            "ontology_source": ontology_source,
            "ontology_label": ontology_label,
            "ontology_description": _clean_reference_text(
                rep.get("ontology_description", "")
            ),
            "ontology_synonyms": "; ".join(ontology_synonyms),
            "confidence": confidence,
            "source_id": source_id,
            "source_name": source_name,
            "source_url": source_url,
            "source_batch_id": source_batch_id,
            "retrieved_at": retrieved_at,
            "source_reference_clean": source_reference_clean,
            "ontology_status": ontology_status,
            "ontology_match_method": clean_str(rep.get("ontology_match_method", "")),
            "ontology_query": clean_str(rep.get("ontology_query", "")),
            "batch_id": batch_id,
            "created_at": now_iso(),
        }

        diseases.append(disease_row)

        alias_bucket: dict[str, dict[str, Any]] = {}

        if seed_name and canonical_key(seed_name) != disease_key:
            _merge_alias_candidate(
                alias_bucket,
                alias_name=seed_name,
                alias_type="seed_name",
                alias_source="seed_disease_name",
                disease_id=disease_id,
                disease_key=disease_key,
                source_id=source_id,
                source_name=source_name,
                source_url=source_url,
                source_batch_id=source_batch_id,
                retrieved_at=retrieved_at,
                confidence=confidence,
                source_reference_clean=source_reference_clean,
                batch_id=batch_id,
            )

        for _, row in group.iterrows():
            row_confidence = _safe_float(
                row.get("ontology_confidence", row.get("confidence", confidence))
            )
            row_source_id = (
                clean_str(row.get("source_id", ""))
                or clean_str(row.get("seed_id", ""))
                or disease_key
            )
            row_source_name = clean_str(row.get("source_name", "")) or source_name
            row_source_url = clean_str(row.get("source_url", "")) or source_url
            row_source_batch_id = (
                clean_str(row.get("source_batch_id", ""))
                or clean_str(row.get("batch_id", ""))
                or source_batch_id
            )
            row_retrieved_at = clean_str(row.get("retrieved_at", "")) or retrieved_at
            row_source_reference_clean = (
                clean_str(row.get("source_reference_clean", ""))
                or source_reference_clean
            )
            row_batch_id = clean_str(row.get("batch_id", "")) or batch_id
            row_ontology_status = clean_str(row.get("ontology_status", ""))
            row_ontology_label = _clean_name_text(
                row.get("ontology_label", "")
            ) or _clean_name_text(row.get("standardized_name", ""))
            row_confident = bool(
                row_ontology_label
                and row_confidence >= confidence_threshold
                and clean_str(row_ontology_status).lower()
                in {"matched", "seed_provided", "cache", "ambiguous"}
            )

            for alias_name, alias_type, alias_source in _detect_alias_sources(
                row, include_ontology_synonyms=row_confident
            ):
                if alias_type == "ontology_synonym" and not row_confident:
                    continue
                _merge_alias_candidate(
                    alias_bucket,
                    alias_name=alias_name,
                    alias_type=alias_type,
                    alias_source=alias_source,
                    disease_id=disease_id,
                    disease_key=disease_key,
                    source_id=row_source_id,
                    source_name=row_source_name,
                    source_url=row_source_url,
                    source_batch_id=row_source_batch_id,
                    retrieved_at=row_retrieved_at,
                    confidence=row_confidence,
                    source_reference_clean=row_source_reference_clean,
                    batch_id=row_batch_id,
                )

            if (
                row_confident
                and row_ontology_label
                and canonical_key(row_ontology_label) != disease_key
            ):
                _merge_alias_candidate(
                    alias_bucket,
                    alias_name=row_ontology_label,
                    alias_type="ontology_label",
                    alias_source="ontology_label",
                    disease_id=disease_id,
                    disease_key=disease_key,
                    source_id=row_source_id,
                    source_name=row_source_name,
                    source_url=row_source_url,
                    source_batch_id=row_source_batch_id,
                    retrieved_at=row_retrieved_at,
                    confidence=row_confidence,
                    source_reference_clean=row_source_reference_clean,
                    batch_id=row_batch_id,
                )

        ordered_aliases = sorted(
            alias_bucket.values(),
            key=lambda item: (
                -int(item["_priority"]),
                clean_str(item["alias_name"]).lower(),
            ),
        )

        for alias in ordered_aliases:
            aliases.append({k: v for k, v in alias.items() if k != "_priority"})

        canonical_alias_name = _clean_name_text(disease_row["disease_name"])
        canonical_alias_key = canonical_key(canonical_alias_name)
        if canonical_alias_name and canonical_alias_key:
            alias_map_rows.append(
                {
                    "alias_map_id": disease_alias_id(disease_id, canonical_alias_key),
                    "alias": canonical_alias_name,
                    "alias_key": canonical_alias_key,
                    "disease_key": disease_key,
                    "disease_id": disease_id,
                    "type": "primary",
                    "source_id": source_id,
                    "source_name": source_name,
                    "source_url": source_url,
                    "source_batch_id": source_batch_id,
                    "retrieved_at": retrieved_at,
                    "confidence": confidence,
                    "created_at": now_iso(),
                }
            )

        seen_map_aliases: set[str] = {canonical_alias_key}
        for alias in ordered_aliases:
            alias_key = clean_str(alias.get("alias_key", ""))
            alias_name = _clean_name_text(alias.get("alias_name", ""))
            alias_type = clean_str(alias.get("alias_type", "")) or "user_alias"
            if not alias_key or not alias_name or alias_key in seen_map_aliases:
                continue
            seen_map_aliases.add(alias_key)

            alias_map_rows.append(
                {
                    "alias_map_id": disease_alias_id(disease_id, alias_key),
                    "alias": alias_name,
                    "alias_key": alias_key,
                    "disease_key": disease_key,
                    "disease_id": disease_id,
                    "type": alias_type,
                    "source_id": clean_str(alias.get("source_id", source_id)),
                    "source_name": clean_str(alias.get("source_name", source_name)),
                    "source_url": clean_str(alias.get("source_url", source_url)),
                    "source_batch_id": clean_str(
                        alias.get("source_batch_id", source_batch_id)
                    ),
                    "retrieved_at": clean_str(alias.get("retrieved_at", retrieved_at)),
                    "confidence": _safe_float(
                        alias.get("confidence", confidence), confidence
                    ),
                    "created_at": clean_str(alias.get("created_at", now_iso())),
                }
            )

    diseases_df = pd.DataFrame(diseases, columns=DISEASE_OUTPUT_COLUMNS)
    aliases_df = pd.DataFrame(aliases, columns=ALIAS_OUTPUT_COLUMNS)
    alias_map_df = pd.DataFrame(alias_map_rows, columns=ALIAS_MAP_COLUMNS)

    diseases_df = diseases_df[DISEASE_OUTPUT_COLUMNS]
    aliases_df = aliases_df[ALIAS_OUTPUT_COLUMNS]
    alias_map_df = alias_map_df[ALIAS_MAP_COLUMNS]

    diseases_path = output_dir / "diseases.csv"
    aliases_path = output_dir / "disease_aliases.csv"
    alias_map_path = output_dir / "disease_alias_map.csv"
    template_path = output_dir / "disease_targets_template.csv"

    write_frame(diseases_df, diseases_path)
    write_frame(aliases_df, aliases_path)
    write_frame(alias_map_df, alias_map_path)

    if bool(
        canonical_cfg.get(
            "write_targets_template",
            export_cfg.get("write_targets_template", True),
        )
    ):
        _make_target_template(template_path)

    manifest = {
        "module_name": settings.get("module_name", "disease_etl"),
        "step": "03_build_canonical",
        "batch_id": clean_str(settings.get("batch_id", "")),
        "input_path": str(input_path),
        "output_dir": str(output_dir),
        "diseases_output": str(diseases_path),
        "aliases_output": str(aliases_path),
        "alias_map_output": str(alias_map_path),
        "targets_template_output": str(template_path) if template_path.exists() else "",
        "disease_count": int(len(diseases_df)),
        "alias_count": int(len(aliases_df)),
        "alias_map_count": int(len(alias_map_df)),
        "confidence_threshold": confidence_threshold,
        "timestamp": now_iso(),
    }

    manifest_path = output_dir / "run_manifest.json"
    with manifest_path.open("w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
        f.write("\n")

    log_path = output_dir / "run.log"
    with log_path.open("w", encoding="utf-8") as f:
        f.write(f"Canonical build completed at {manifest['timestamp']}\n")
        f.write(f"Input: {input_path}\n")
        f.write(f"Diseases: {diseases_path}\n")
        f.write(f"Aliases: {aliases_path}\n")
        f.write(f"Alias map: {alias_map_path}\n")
        if template_path.exists():
            f.write(f"Targets template: {template_path}\n")
        f.write(f"Disease rows: {len(diseases_df)}\n")
        f.write(f"Alias rows: {len(aliases_df)}\n")
        f.write(f"Alias map rows: {len(alias_map_df)}\n")
        f.write(f"Confidence threshold: {confidence_threshold}\n")

    logger.info(
        "Built canonical tables: %s diseases, %s aliases, %s alias-map rows",
        len(diseases_df),
        len(aliases_df),
        len(alias_map_df),
    )

    return manifest


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Build canonical disease and alias tables from ontology-enriched disease rows."
    )
    parser.add_argument(
        "--settings",
        default=str(DEFAULT_SETTINGS_PATH),
        help="Path to the pipeline settings.yml file (default: diseases/settings.yml)",
    )
    args = parser.parse_args()
    run(args.settings)


if __name__ == "__main__":
    main()
