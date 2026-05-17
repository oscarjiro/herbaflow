"""Deduplicate normalized compound evidence into unique compound candidate clusters.

Purpose
-------
This script is the candidate-deduplication step of the compound ETL pipeline. It
consumes the normalized compound staging output from `02_normalize`, combines it
with the review output as an evidence-aware overlay, and groups rows into unique
compound candidate clusters before external enrichment.

Why this step exists
--------------------
The raw source is many-to-many plant-compound evidence, not canonical compound data.
The same compound may appear across multiple plants, with naming variation, minor
CAS typos, or review flags from normalization. This step reduces duplicate search
work for PubChem / ChEMBL by clustering evidence rows into candidate compounds
while keeping uncertainty visible.

Inputs
------
- `compounds/02_normalize/out/compounds_normalized.csv`
- `compounds/02_normalize/out/compound_review.csv`
- `compounds/02_normalize/out/plant_mapping_resolution.csv`
- Settings from `settings.yml`

Outputs
-------
Written only to `compounds/03_dedupe_candidates/out/`:
- `compound_candidates.csv`
- `compound_candidate_members.csv`
- `compound_candidate_review.csv`
- `dedupe_summary.json`
- log file in `out/logs/`

Behavior
--------
- Combines normalized ready rows and review rows without dropping evidence.
- Resolves plant mappings again when the mapping resolution file provides a better
  canonical plant ID or mapping metadata.
- Groups evidence into deterministic candidate clusters using pre-enrichment
  chemistry signals such as normalized CAS, name, formula, and molecular weight.
- Does not query PubChem or ChEMBL.
- Does not create final canonical compound IDs.
- Preserves raw provenance and normalized evidence for later enrichment and
  canonical building.
- Is idempotent and safe to rerun with the same input and settings.

Downstream contract
-------------------
`04_enrich` should consume `compound_candidates.csv` as the unit of enrichment,
not the raw normalized evidence rows. Candidate-member links are preserved in
`compound_candidate_members.csv` so enrichment results can later be propagated
back to all supporting evidence rows.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging as shared_setup_logging, ensure_dir, normalize_whitespace, to_key, make_run_id, write_csv, write_json, now_iso

import argparse
import csv
import hashlib
import json
import logging
import math
import re
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional, Sequence, Tuple


NORMALIZED_COLUMNS = [
    "plant_id",
    "c_id",
    "cas_id",
    "metabolite",
    "molecular_formula",
    "mw",
    "organism",
    "normalized_metabolite_name",
    "normalized_metabolite_key",
    "normalized_cas_id",
    "normalized_cas_key",
    "cas_is_valid",
    "cas_validation_reason",
    "normalized_formula",
    "normalized_formula_key",
    "normalized_mw",
    "source_compound_key",
    "raw_plant_key",
    "canonical_plant_id",
    "plant_mapping_status",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
    "raw_line_number",
    "raw_row_hash",
    "normalization_status",
    "review_reason",
]

MEMBER_OUTPUT_COLUMNS = [
    "compound_candidate_member_id",
    "compound_candidate_id",
    "normalized_source_row_id",
    "source_compound_key",
    "plant_id",
    "canonical_plant_id",
    "raw_plant_key",
    "c_id",
    "cas_id",
    "metabolite",
    "normalized_metabolite_name",
    "normalized_metabolite_key",
    "normalized_cas_id",
    "normalized_cas_key",
    "normalized_formula",
    "normalized_formula_key",
    "normalized_mw",
    "normalization_status",
    "review_reason",
    "candidate_key",
    "candidate_key_strategy",
    "candidate_confidence",
    "candidate_status",
    "source_name",
    "source_batch_id",
    "retrieved_at",
]

CANDIDATE_OUTPUT_COLUMNS = [
    "compound_candidate_id",
    "candidate_key",
    "candidate_key_strategy",
    "representative_name",
    "representative_name_key",
    "representative_cas_id",
    "representative_cas_key",
    "representative_formula",
    "representative_formula_key",
    "representative_mw",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
    "candidate_status",
    "candidate_confidence",
    "member_count",
    "ready_member_count",
    "review_member_count",
    "search_priority",
    "search_terms_json",
    "candidate_fingerprint",
    "review_reason",
]

REVIEW_OUTPUT_COLUMNS = [
    "compound_candidate_id",
    "candidate_key",
    "candidate_key_strategy",
    "candidate_status",
    "candidate_confidence",
    "member_count",
    "ready_member_count",
    "review_member_count",
    "representative_name",
    "representative_cas_id",
    "representative_formula",
    "representative_mw",
    "review_reason",
    "evidence_summary_json",
    "source_name",
    "source_batch_id",
    "retrieved_at",
]

PLANT_RAW_ID_CANDIDATES = [
    "source_plant_raw_id",
    "raw_plant_id",
    "original_plant_id",
    "knapsack_plant_id",
    "source_plant_id",
    "scraped_plant_id",
    "source_id",
    "plant_id",
]

PLANT_CANONICAL_ID_CANDIDATES = ["plant_id", "canonical_plant_id"]


def setup_logging(log_dir: Path, run_id: str) -> Path:
    ensure_dir(log_dir)
    log_path = log_dir / f"dedupe_compound_candidates_{run_id}.log"

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root_logger.addHandler(stream_handler)
    root_logger.addHandler(file_handler)
    return log_path


def stable_hash(payload: Dict[str, Any]) -> str:
    """SHA-256 dedup fingerprint — kept as SHA-256 intentionally."""
    canonical_json = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def stable_timestamp(batch_id: str) -> str:
    if batch_id and batch_id != "auto":
        return batch_id
    return now_iso()


def parse_float(value: Optional[str]) -> Optional[float]:
    text = normalize_whitespace(value)
    if not text:
        return None
    try:
        num = float(text)
    except ValueError:
        return None
    if math.isnan(num) or math.isinf(num):
        return None
    return num


def mw_bucket(value: Optional[str]) -> str:
    num = parse_float(value)
    if num is None:
        return ""
    return f"{round(num, 1):.1f}"


def ensure_columns(
    fieldnames: Sequence[str], required: Sequence[str], label: str
) -> None:
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise ValueError(f"{label} is missing expected columns: {missing}")


def read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"File has no header row: {path}")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def load_plant_mapping(
    mapping_file: Optional[Path],
) -> Tuple[Dict[str, Dict[str, str]], Dict[str, Any]]:
    mapping: Dict[str, Dict[str, str]] = {}
    meta: Dict[str, Any] = {
        "loaded": False,
        "mapping_file": str(mapping_file) if mapping_file else "",
        "row_count": 0,
        "mapped_rows": 0,
    }
    if not mapping_file or not mapping_file.exists():
        return mapping, meta

    rows, fieldnames = read_csv_rows(mapping_file)
    if not rows:
        return mapping, meta

    canonical_col = next(
        (c for c in PLANT_CANONICAL_ID_CANDIDATES if c in fieldnames), None
    )
    raw_col = next((c for c in PLANT_RAW_ID_CANDIDATES if c in fieldnames), None)
    if canonical_col is None or raw_col is None:
        meta["reason"] = "mapping columns not found"
        return mapping, meta

    for row in rows:
        meta["row_count"] += 1
        raw_key = to_key(row.get(raw_col, ""))
        canonical_id = normalize_whitespace(row.get(canonical_col, ""))
        if not raw_key or not canonical_id:
            continue
        mapping[raw_key] = {
            "canonical_plant_id": canonical_id,
            "plant_mapping_status": "mapped",
            "plant_mapping_confidence": "1.0",
            "plant_mapping_source": "PlantETL",
            "plant_mapping_source_column": raw_col,
            "plant_mapping_canonical_column": canonical_col,
        }
    meta["loaded"] = True
    meta["mapped_rows"] = len(mapping)
    meta["raw_column"] = raw_col
    meta["canonical_column"] = canonical_col
    return mapping, meta


def merge_mapping_into_rows(
    rows: List[Dict[str, Any]], mapping: Dict[str, Dict[str, str]]
) -> List[Dict[str, Any]]:
    if not mapping:
        return rows

    merged: List[Dict[str, Any]] = []
    for row in rows:
        raw_key = to_key(row.get("raw_plant_key") or row.get("plant_id") or "")
        hit = mapping.get(raw_key)
        if hit:
            updated = dict(row)
            if not normalize_whitespace(updated.get("canonical_plant_id", "")):
                updated["canonical_plant_id"] = hit.get("canonical_plant_id", "")
            if (
                not normalize_whitespace(updated.get("plant_mapping_status", ""))
                or updated.get("plant_mapping_status") == "unmapped"
            ):
                updated["plant_mapping_status"] = hit.get(
                    "plant_mapping_status", "mapped"
                )
            updated["plant_mapping_confidence"] = hit.get(
                "plant_mapping_confidence", updated.get("plant_mapping_confidence", "")
            )
            updated["plant_mapping_source"] = hit.get(
                "plant_mapping_source", updated.get("plant_mapping_source", "")
            )
            updated["plant_mapping_source_column"] = hit.get(
                "plant_mapping_source_column",
                updated.get("plant_mapping_source_column", ""),
            )
            updated["plant_mapping_canonical_column"] = hit.get(
                "plant_mapping_canonical_column",
                updated.get("plant_mapping_canonical_column", ""),
            )
            merged.append(updated)
        else:
            merged.append(row)
    return merged


def overlay_review_rows(
    base_rows: List[Dict[str, Any]], review_rows: List[Dict[str, str]]
) -> List[Dict[str, Any]]:
    """Use the review CSV as an overlay rather than a duplicate source of truth."""
    if not review_rows:
        return base_rows

    index: Dict[str, Dict[str, Any]] = {}
    for row in base_rows:
        rid = normalize_whitespace(
            row.get("raw_row_hash") or row.get("source_compound_key") or ""
        )
        if rid:
            index[rid] = row

    for review in review_rows:
        rid = normalize_whitespace(
            review.get("raw_row_hash") or review.get("source_compound_key") or ""
        )
        if not rid:
            continue
        if rid in index:
            existing = index[rid]
            existing["normalization_status"] = "review"
            existing["review_reason"] = normalize_whitespace(
                review.get("review_reason") or existing.get("review_reason") or ""
            )
            if not normalize_whitespace(existing.get("candidate_review_source", "")):
                existing["candidate_review_source"] = "compound_review.csv"
        else:
            review_copy = dict(review)
            review_copy.setdefault("candidate_review_source", "compound_review.csv")
            review_copy.setdefault("normalization_status", "review")
            index[rid] = review_copy

    ordered: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for row in base_rows:
        rid = normalize_whitespace(
            row.get("raw_row_hash") or row.get("source_compound_key") or ""
        )
        if rid and rid in index and rid not in seen:
            ordered.append(index[rid])
            seen.add(rid)
        elif not rid:
            ordered.append(row)
    for rid, row in index.items():
        if rid not in seen:
            ordered.append(row)
            seen.add(rid)
    return ordered


def build_candidate_signature(
    row: Dict[str, Any],
) -> Tuple[str, str, float, List[str], int]:
    """Build a deterministic pre-enrichment candidate signature."""
    cas_key = normalize_whitespace(row.get("normalized_cas_key", ""))
    name_key = normalize_whitespace(row.get("normalized_metabolite_key", ""))
    formula_key = normalize_whitespace(row.get("normalized_formula_key", ""))
    mw_bin = mw_bucket(row.get("normalized_mw", ""))
    source_compound_key = normalize_whitespace(row.get("source_compound_key", ""))
    normalized_cas_id = normalize_whitespace(row.get("normalized_cas_id", ""))
    cas_is_valid = normalize_whitespace(row.get("cas_is_valid", "")).lower() == "true"

    search_terms: List[str] = []
    for term in [
        row.get("normalized_metabolite_name"),
        row.get("metabolite"),
        normalized_cas_id,
        row.get("cas_id"),
        row.get("normalized_formula"),
        row.get("molecular_formula"),
    ]:
        t = normalize_whitespace(term)
        if t and t not in search_terms:
            search_terms.append(t)

    if cas_key and cas_is_valid:
        strategy = "cas_exact"
        candidate_key = f"cas::{cas_key}"
        confidence = 0.98
        priority = 1
        if name_key:
            candidate_key = f"cas_name::{cas_key}::{name_key}"
            strategy = "cas_exact_name_support"
            confidence = 0.985
        if formula_key:
            candidate_key = (
                f"cas_name_formula::{cas_key}::{name_key or 'na'}::{formula_key}"
            )
            strategy = "cas_exact_name_formula_support"
            confidence = 0.99
        return strategy, candidate_key, confidence, search_terms, priority

    if name_key and formula_key and mw_bin:
        return (
            "name_formula_mw",
            f"name_formula_mw::{name_key}::{formula_key}::{mw_bin}",
            0.88,
            search_terms,
            2,
        )

    if name_key and cas_key:
        return (
            "name_cas",
            f"name_cas::{name_key}::{cas_key}",
            0.86,
            search_terms,
            2,
        )

    if formula_key and mw_bin:
        return (
            "formula_mw",
            f"formula_mw::{formula_key}::{mw_bin}",
            0.80,
            search_terms,
            3,
        )

    if name_key and formula_key:
        return (
            "name_formula",
            f"name_formula::{name_key}::{formula_key}",
            0.78,
            search_terms,
            3,
        )

    if name_key and mw_bin:
        return (
            "name_mw",
            f"name_mw::{name_key}::{mw_bin}",
            0.72,
            search_terms,
            4,
        )

    if name_key:
        return (
            "name_only",
            f"name::{name_key}",
            0.62,
            search_terms,
            5,
        )

    if cas_key:
        return (
            "cas_unverified",
            f"cas_unverified::{cas_key}",
            0.55,
            search_terms,
            5,
        )

    if formula_key:
        return (
            "formula_only",
            f"formula::{formula_key}",
            0.50,
            search_terms,
            6,
        )

    return (
        "source_compound_key",
        f"source::{source_compound_key or stable_hash({'source_compound_key': source_compound_key, 'raw_row_hash': row.get('raw_row_hash', '')})}",
        0.40,
        search_terms,
        7,
    )


def confidence_adjustment(
    strategy: str, members: List[Dict[str, Any]]
) -> Tuple[float, str]:
    """Adjust base confidence based on evidence consistency and support."""
    base = members[0]["candidate_confidence_base"] if members else 0.0
    support_bonus = min(0.08, 0.02 * max(0, len(members) - 1))
    review_penalty = 0.0
    conflict_penalty = 0.0

    statuses = [
        normalize_whitespace(m.get("normalization_status", "")).lower() for m in members
    ]
    if any(status == "review" for status in statuses) and strategy not in {
        "cas_exact",
        "cas_exact_name_support",
        "cas_exact_name_formula_support",
    }:
        review_penalty = 0.05

    distinct_name_keys = {
        normalize_whitespace(m.get("normalized_metabolite_key", ""))
        for m in members
        if normalize_whitespace(m.get("normalized_metabolite_key", ""))
    }
    distinct_cas_keys = {
        normalize_whitespace(m.get("normalized_cas_key", ""))
        for m in members
        if normalize_whitespace(m.get("normalized_cas_key", ""))
    }
    distinct_formula_keys = {
        normalize_whitespace(m.get("normalized_formula_key", ""))
        for m in members
        if normalize_whitespace(m.get("normalized_formula_key", ""))
    }

    if strategy.startswith("cas_exact"):
        if len(distinct_cas_keys) > 1:
            conflict_penalty += 0.30
        if len(distinct_name_keys) > 2:
            conflict_penalty += 0.10
    elif strategy in {"name_formula_mw", "name_formula", "name_mw", "name_only"}:
        if len(distinct_name_keys) > 1:
            conflict_penalty += 0.20
        if len(distinct_formula_keys) > 1:
            conflict_penalty += 0.15
        if len(distinct_cas_keys) > 1:
            conflict_penalty += 0.10
    elif strategy in {"formula_mw", "formula_only"}:
        if len(distinct_formula_keys) > 1:
            conflict_penalty += 0.20
        if len(distinct_name_keys) > 1:
            conflict_penalty += 0.10
    else:
        if len(distinct_name_keys) > 1:
            conflict_penalty += 0.10
        if len(distinct_cas_keys) > 1:
            conflict_penalty += 0.10

    score = max(0.0, min(1.0, base + support_bonus - review_penalty - conflict_penalty))
    reason_parts = []
    if support_bonus:
        reason_parts.append(f"support_bonus={support_bonus:.2f}")
    if review_penalty:
        reason_parts.append(f"review_penalty={review_penalty:.2f}")
    if conflict_penalty:
        reason_parts.append(f"conflict_penalty={conflict_penalty:.2f}")
    return score, ";".join(reason_parts)


def decide_candidate_status(
    strategy: str,
    confidence: float,
    members: List[Dict[str, Any]],
    min_ready_confidence: float,
) -> Tuple[str, str]:
    statuses = [
        normalize_whitespace(m.get("normalization_status", "")).lower() for m in members
    ]
    distinct_name_keys = {
        normalize_whitespace(m.get("normalized_metabolite_key", ""))
        for m in members
        if normalize_whitespace(m.get("normalized_metabolite_key", ""))
    }
    distinct_cas_keys = {
        normalize_whitespace(m.get("normalized_cas_key", ""))
        for m in members
        if normalize_whitespace(m.get("normalized_cas_key", ""))
    }
    distinct_formula_keys = {
        normalize_whitespace(m.get("normalized_formula_key", ""))
        for m in members
        if normalize_whitespace(m.get("normalized_formula_key", ""))
    }

    conflict = False
    conflict_reasons: List[str] = []

    if strategy.startswith("cas_exact") and len(distinct_cas_keys) > 1:
        conflict = True
        conflict_reasons.append("multiple_cas_keys")
    if (
        strategy in {"name_formula_mw", "name_formula", "name_mw", "name_only"}
        and len(distinct_name_keys) > 1
    ):
        conflict = True
        conflict_reasons.append("multiple_name_keys")
    if strategy in {"formula_mw", "formula_only"} and len(distinct_formula_keys) > 1:
        conflict = True
        conflict_reasons.append("multiple_formula_keys")
    if strategy == "source_compound_key" and len(members) > 1:
        conflict = True
        conflict_reasons.append("multiple_source_records_only")

    if conflict:
        return "ambiguous", ";".join(conflict_reasons)
    if confidence < min_ready_confidence:
        return "review", f"confidence_below_threshold_{min_ready_confidence:.2f}"
    if any(status == "review" for status in statuses) and strategy in {
        "name_only",
        "cas_unverified",
        "formula_only",
        "source_compound_key",
    }:
        return "review", "contains_review_evidence"
    return "ready", ""


def candidate_id_from_key(candidate_key: str) -> str:
    return f"cmpcand_{hashlib.sha256(candidate_key.encode('utf-8')).hexdigest()[:16]}"


def member_id_from(candidate_id: str, normalized_source_row_id: str) -> str:
    return f"cmpcandm_{hashlib.sha256(f'{candidate_id}|{normalized_source_row_id}'.encode('utf-8')).hexdigest()[:16]}"


def build_candidate_records(
    rows: List[Dict[str, Any]],
    min_ready_confidence: float,
    source_name: str,
    source_url: str,
    batch_id: str,
    run_id: str,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], List[Dict[str, Any]]]:
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    signature_meta: Dict[str, Dict[str, Any]] = {}

    for row in rows:
        strategy, candidate_key, base_confidence, search_terms, search_priority = (
            build_candidate_signature(row)
        )
        candidate_row = dict(row)
        candidate_row["candidate_key_strategy"] = strategy
        candidate_row["candidate_key"] = candidate_key
        candidate_row["candidate_confidence_base"] = base_confidence
        candidate_row["candidate_search_terms"] = search_terms
        candidate_row["candidate_search_priority"] = search_priority
        grouped[candidate_key].append(candidate_row)
        signature_meta[candidate_key] = {
            "strategy": strategy,
            "base_confidence": base_confidence,
            "search_terms": search_terms,
            "search_priority": search_priority,
        }

    candidate_rows: List[Dict[str, Any]] = []
    member_rows: List[Dict[str, Any]] = []
    review_rows: List[Dict[str, Any]] = []
    retrieved_at = stable_timestamp(batch_id)

    for candidate_key in sorted(grouped.keys()):
        members = grouped[candidate_key]
        members_sorted = sorted(
            members,
            key=lambda r: (
                normalize_whitespace(r.get("source_batch_id", "")),
                normalize_whitespace(r.get("raw_row_hash", "")),
                normalize_whitespace(r.get("source_compound_key", "")),
            ),
        )
        strategy = signature_meta[candidate_key]["strategy"]
        base_confidence = signature_meta[candidate_key]["base_confidence"]
        search_terms = signature_meta[candidate_key]["search_terms"]
        search_priority = signature_meta[candidate_key]["search_priority"]

        confidence, confidence_reason = confidence_adjustment(strategy, members_sorted)
        confidence = max(0.0, min(1.0, confidence))
        candidate_status, status_reason = decide_candidate_status(
            strategy, confidence, members_sorted, min_ready_confidence
        )

        distinct_names = [
            normalize_whitespace(m.get("normalized_metabolite_name", ""))
            for m in members_sorted
            if normalize_whitespace(m.get("normalized_metabolite_name", ""))
        ]
        distinct_cas = [
            normalize_whitespace(m.get("normalized_cas_id", ""))
            for m in members_sorted
            if normalize_whitespace(m.get("normalized_cas_id", ""))
        ]
        distinct_formulas = [
            normalize_whitespace(m.get("normalized_formula", ""))
            for m in members_sorted
            if normalize_whitespace(m.get("normalized_formula", ""))
        ]
        distinct_mw = [
            normalize_whitespace(m.get("normalized_mw", ""))
            for m in members_sorted
            if normalize_whitespace(m.get("normalized_mw", ""))
        ]

        representative_name = (
            Counter(distinct_names).most_common(1)[0][0] if distinct_names else ""
        )
        representative_cas = (
            Counter(distinct_cas).most_common(1)[0][0] if distinct_cas else ""
        )
        representative_formula = (
            Counter(distinct_formulas).most_common(1)[0][0] if distinct_formulas else ""
        )
        representative_mw = (
            Counter(distinct_mw).most_common(1)[0][0] if distinct_mw else ""
        )

        representative_name_key = to_key(representative_name)
        representative_cas_key = to_key(representative_cas)
        representative_formula_key = to_key(representative_formula)

        candidate_id = candidate_id_from_key(candidate_key)
        member_count = len(members_sorted)
        ready_member_count = sum(
            1
            for m in members_sorted
            if normalize_whitespace(m.get("normalization_status", "")).lower()
            == "ready"
        )
        review_member_count = member_count - ready_member_count

        combined_terms: List[str] = []
        for term in [
            representative_name,
            representative_cas,
            representative_formula,
            representative_mw,
        ]:
            t = normalize_whitespace(term)
            if t and t not in combined_terms:
                combined_terms.append(t)
        for term in search_terms:
            if term and term not in combined_terms:
                combined_terms.append(term)

        candidate_fingerprint = stable_hash(
            {
                "candidate_key": candidate_key,
                "candidate_id": candidate_id,
                "member_source_row_ids": sorted(
                    normalize_whitespace(
                        m.get("raw_row_hash") or m.get("source_compound_key") or ""
                    )
                    for m in members_sorted
                ),
                "representative_name": representative_name,
                "representative_cas": representative_cas,
                "representative_formula": representative_formula,
                "representative_mw": representative_mw,
            }
        )

        review_reason_parts = []
        if status_reason:
            review_reason_parts.append(status_reason)
        if confidence_reason:
            review_reason_parts.append(confidence_reason)
        if review_member_count:
            review_reason_parts.append(f"review_members={review_member_count}")
        review_reason = ";".join([p for p in review_reason_parts if p])

        candidate_rows.append(
            {
                "compound_candidate_id": candidate_id,
                "candidate_key": candidate_key,
                "candidate_key_strategy": strategy,
                "representative_name": representative_name,
                "representative_name_key": representative_name_key,
                "representative_cas_id": representative_cas,
                "representative_cas_key": representative_cas_key,
                "representative_formula": representative_formula,
                "representative_formula_key": representative_formula_key,
                "representative_mw": representative_mw,
                "source_name": source_name,
                "source_url": source_url,
                "source_batch_id": run_id,
                "retrieved_at": retrieved_at,
                "candidate_status": candidate_status,
                "candidate_confidence": f"{confidence:.4f}",
                "member_count": str(member_count),
                "ready_member_count": str(ready_member_count),
                "review_member_count": str(review_member_count),
                "search_priority": str(search_priority),
                "search_terms_json": json.dumps(combined_terms, ensure_ascii=False),
                "candidate_fingerprint": candidate_fingerprint,
                "review_reason": review_reason,
            }
        )

        for member in members_sorted:
            normalized_source_row_id = normalize_whitespace(
                member.get("raw_row_hash") or member.get("source_compound_key") or ""
            )
            member_rows.append(
                {
                    "compound_candidate_member_id": member_id_from(
                        candidate_id, normalized_source_row_id
                    ),
                    "compound_candidate_id": candidate_id,
                    "normalized_source_row_id": normalized_source_row_id,
                    "source_compound_key": normalize_whitespace(
                        member.get("source_compound_key", "")
                    ),
                    "plant_id": normalize_whitespace(member.get("plant_id", "")),
                    "canonical_plant_id": normalize_whitespace(
                        member.get("canonical_plant_id", "")
                    ),
                    "raw_plant_key": normalize_whitespace(
                        member.get("raw_plant_key", "")
                    ),
                    "c_id": normalize_whitespace(member.get("c_id", "")),
                    "cas_id": normalize_whitespace(member.get("cas_id", "")),
                    "metabolite": normalize_whitespace(member.get("metabolite", "")),
                    "normalized_metabolite_name": normalize_whitespace(
                        member.get("normalized_metabolite_name", "")
                    ),
                    "normalized_metabolite_key": normalize_whitespace(
                        member.get("normalized_metabolite_key", "")
                    ),
                    "normalized_cas_id": normalize_whitespace(
                        member.get("normalized_cas_id", "")
                    ),
                    "normalized_cas_key": normalize_whitespace(
                        member.get("normalized_cas_key", "")
                    ),
                    "normalized_formula": normalize_whitespace(
                        member.get("normalized_formula", "")
                    ),
                    "normalized_formula_key": normalize_whitespace(
                        member.get("normalized_formula_key", "")
                    ),
                    "normalized_mw": normalize_whitespace(
                        member.get("normalized_mw", "")
                    ),
                    "normalization_status": normalize_whitespace(
                        member.get("normalization_status", "")
                    ),
                    "review_reason": normalize_whitespace(
                        member.get("review_reason", "")
                    ),
                    "candidate_key": candidate_key,
                    "candidate_key_strategy": strategy,
                    "candidate_confidence": f"{confidence:.4f}",
                    "candidate_status": candidate_status,
                    "source_name": source_name,
                    "source_batch_id": normalize_whitespace(
                        member.get("source_batch_id", run_id)
                    )
                    or run_id,
                    "retrieved_at": normalize_whitespace(
                        member.get("retrieved_at", retrieved_at)
                    )
                    or retrieved_at,
                }
            )

        if candidate_status != "ready":
            evidence_summary = {
                "candidate_key": candidate_key,
                "strategy": strategy,
                "member_count": member_count,
                "ready_member_count": ready_member_count,
                "review_member_count": review_member_count,
                "distinct_names": sorted(set(distinct_names)),
                "distinct_cas": sorted(set(distinct_cas)),
                "distinct_formulas": sorted(set(distinct_formulas)),
                "distinct_mw": sorted(set(distinct_mw)),
            }
            review_rows.append(
                {
                    "compound_candidate_id": candidate_id,
                    "candidate_key": candidate_key,
                    "candidate_key_strategy": strategy,
                    "candidate_status": candidate_status,
                    "candidate_confidence": f"{confidence:.4f}",
                    "member_count": str(member_count),
                    "ready_member_count": str(ready_member_count),
                    "review_member_count": str(review_member_count),
                    "representative_name": representative_name,
                    "representative_cas_id": representative_cas,
                    "representative_formula": representative_formula,
                    "representative_mw": representative_mw,
                    "review_reason": review_reason,
                    "evidence_summary_json": json.dumps(
                        evidence_summary, ensure_ascii=False
                    ),
                    "source_name": source_name,
                    "source_batch_id": run_id,
                    "retrieved_at": retrieved_at,
                }
            )

    candidate_rows.sort(key=lambda r: (r["candidate_key"], r["compound_candidate_id"]))
    member_rows.sort(
        key=lambda r: (
            r["compound_candidate_id"],
            r["normalized_source_row_id"],
            r["compound_candidate_member_id"],
        )
    )
    review_rows.sort(key=lambda r: (r["candidate_key"], r["compound_candidate_id"]))
    return candidate_rows, member_rows, review_rows


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Deduplicate normalized compound evidence into candidate clusters."
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to the compound ETL settings.yml file.",
    )
    parser.add_argument(
        "--input",
        type=str,
        default="",
        help="Optional override for the normalized compounds CSV.",
    )
    parser.add_argument(
        "--review-input",
        type=str,
        default="",
        help="Optional override for the normalization review CSV.",
    )
    parser.add_argument(
        "--mapping-input",
        type=str,
        default="",
        help="Optional override for the plant mapping resolution CSV.",
    )
    args = parser.parse_args()

    cfg = load_settings("compounds")
    run_id = make_run_id("compounds")

    paths = cfg.get("paths", {})
    step_dirs = paths.get("step_dirs", {})
    source_cfg = cfg.get("source", {})
    matching_cfg = cfg.get("matching", {})
    validation_cfg = cfg.get("validation", {})
    thresholds = validation_cfg.get("thresholds", {})

    normalize_out_dir = ETL_ROOT / step_dirs["normalize_out"]
    dedupe_out_dir = ETL_ROOT / step_dirs["dedupe_candidates_out"]
    dedupe_log_dir = dedupe_out_dir / "logs"

    source_name = str(source_cfg.get("name", "KNApSAcK"))
    source_url = str(source_cfg.get("url", ""))
    batch_id = str(source_cfg.get("batch_id", "auto"))
    min_ready_confidence = float(
        thresholds.get("min_compound_confidence_to_auto_accept", 0.70)
    )

    log_path = setup_logging(dedupe_log_dir, run_id)
    log = logging.getLogger("compounds.03_dedupe_candidates")

    normalized_input = (
        Path(args.input).resolve() if args.input else normalize_out_dir / "compounds_normalized.csv"
    )
    review_input = (
        Path(args.review_input).resolve()
        if args.review_input
        else normalize_out_dir / "compound_review.csv"
    )
    mapping_input = (
        Path(args.mapping_input).resolve()
        if args.mapping_input
        else normalize_out_dir / "plant_mapping_resolution.csv"
    )

    log.info("Starting compound candidate dedupe run_id=%s", run_id)
    log.info("Normalized input: %s", normalized_input)
    log.info("Review input: %s", review_input)
    log.info("Mapping input: %s", mapping_input)

    if not normalized_input.exists():
        raise FileNotFoundError(f"Normalized input file not found: {normalized_input}")

    normalized_rows_raw, normalized_fieldnames = read_csv_rows(normalized_input)
    ensure_columns(
        normalized_fieldnames, NORMALIZED_COLUMNS, "compounds_normalized.csv"
    )

    review_rows_raw: List[Dict[str, str]] = []
    if review_input.exists():
        review_rows_raw, review_fieldnames = read_csv_rows(review_input)
        ensure_columns(review_fieldnames, NORMALIZED_COLUMNS, "compound_review.csv")
    else:
        log.info(
            "Review input file not found; continuing without overlay: %s", review_input
        )

    mapping_rows, mapping_meta = load_plant_mapping(mapping_input)
    log.info(
        "Plant mapping metadata: %s", json.dumps(mapping_meta, ensure_ascii=False)
    )

    combined_rows = overlay_review_rows(normalized_rows_raw, review_rows_raw)
    combined_rows = merge_mapping_into_rows(combined_rows, mapping_rows)

    cleaned_rows: List[Dict[str, Any]] = []
    for row in combined_rows:
        cleaned = {
            k: normalize_whitespace(row.get(k, ""))
            for k in NORMALIZED_COLUMNS
            if k in row or k in NORMALIZED_COLUMNS
        }
        for extra_key, extra_value in row.items():
            if extra_key not in cleaned:
                cleaned[extra_key] = normalize_whitespace(extra_value)
        cleaned_rows.append(cleaned)

    candidate_rows, member_rows, review_candidate_rows = build_candidate_records(
        cleaned_rows, min_ready_confidence, source_name, source_url, batch_id, run_id
    )

    ensure_dir(dedupe_out_dir)
    out_candidates = dedupe_out_dir / "compound_candidates.csv"
    out_members = dedupe_out_dir / "compound_candidate_members.csv"
    out_review = dedupe_out_dir / "compound_candidate_review.csv"
    out_summary = dedupe_out_dir / "dedupe_summary.json"

    write_csv(candidate_rows, out_candidates, CANDIDATE_OUTPUT_COLUMNS)
    write_csv(member_rows, out_members, MEMBER_OUTPUT_COLUMNS)
    write_csv(review_candidate_rows, out_review, REVIEW_OUTPUT_COLUMNS)

    total_input_rows = len(cleaned_rows)
    candidate_count = len(candidate_rows)
    merged_clusters = sum(1 for c in candidate_rows if int(c["member_count"]) > 1)
    ambiguous_clusters = sum(
        1 for c in candidate_rows if c["candidate_status"] == "ambiguous"
    )
    review_clusters = sum(1 for c in candidate_rows if c["candidate_status"] != "ready")
    ready_clusters = sum(1 for c in candidate_rows if c["candidate_status"] == "ready")

    summary = {
        "module": "compounds",
        "step": "03_dedupe_candidates",
        "run_id": run_id,
        "normalized_input_file": str(normalized_input),
        "review_input_file": str(review_input),
        "mapping_input_file": str(mapping_input),
        "output_candidates_file": str(out_candidates),
        "output_members_file": str(out_members),
        "output_review_file": str(out_review),
        "log_file": str(log_path),
        "input_row_count": total_input_rows,
        "candidate_cluster_count": candidate_count,
        "candidate_member_row_count": len(member_rows),
        "candidate_review_row_count": len(review_candidate_rows),
        "ready_clusters": ready_clusters,
        "review_clusters": review_clusters,
        "merged_clusters": merged_clusters,
        "ambiguous_clusters": ambiguous_clusters,
        "normalized_ready_rows": sum(
            1
            for r in cleaned_rows
            if normalize_whitespace(r.get("normalization_status", "")).lower()
            == "ready"
        ),
        "normalized_review_rows": sum(
            1
            for r in cleaned_rows
            if normalize_whitespace(r.get("normalization_status", "")).lower()
            == "review"
        ),
        "mapping_meta": mapping_meta,
        "generated_at": now_iso(),
    }
    write_json(summary, out_summary)

    log.info("Input rows: %d", total_input_rows)
    log.info("Candidate clusters: %d", candidate_count)
    log.info("Member rows: %d", len(member_rows))
    log.info("Review clusters: %d", review_clusters)
    log.info("Ambiguous clusters: %d", ambiguous_clusters)
    log.info("Output candidates: %s", out_candidates)
    log.info("Output members: %s", out_members)
    log.info("Output review: %s", out_review)
    log.info("Summary: %s", out_summary)
    log.info("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
