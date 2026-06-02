"""Build final canonical compound seed tables and plant-compound bridges.

Purpose
-------
This script is the canonicalization step of the compound ETL pipeline. It consumes
the enrichment outputs from `04_enrich`, combines them with deduplicated candidate
membership evidence from `03_dedupe_candidates`, and produces the final canonical
seed-layer tables for compounds, aliases, and plant-compound links.

Inputs
------
Required inputs from previous steps:
- `compounds/04_enrich/out/compound_enrichment_results.csv`
- `compounds/04_enrich/out/compound_enrichment_member_map.csv`
- `compounds/04_enrich/out/compound_enrichment_review.csv`
- `compounds/03_dedupe_candidates/out/compound_candidates.csv`
- `compounds/03_dedupe_candidates/out/compound_candidate_members.csv`
- settings from `settings.yml`

Optional inputs:
- `compounds/04_enrich/out/compound_enrichment_cache.csv`
- `compounds/04_enrich/out/enrich_summary.json`

Outputs
-------
Written only to `compounds/05_build_canonical/out/`:
- `compounds.csv`
- `compound_aliases.csv`
- `plant_compounds.csv`
- `compound_review.csv`
- `build_canonical_summary.json`
- log file in `out/logs/`

Behavior
--------
- Selects the final canonical compound row per unique chemical identity.
- Uses enrichment outputs as the final decision layer before validation/export.
- Does not query PubChem or ChEMBL.
- Supports accepted, provisional, review, and unresolved decision states.
- Salvages genuinely useful ambiguous/conflict/review rows when identity evidence is strong enough.
- Builds stable deterministic IDs from canonical chemistry keys.
- Creates a smaller, higher-value alias table by deduplicating aggressively and capping noise.
- Creates a final many-to-many bridge between canonical plants and canonical compounds.
- Preserves provenance and source traceability.
- Is idempotent and safe to rerun.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings as shared_load_settings, ensure_dir, normalize_whitespace, make_run_id, now_iso
from compounds.utils import (
    compound_id_from_key as make_compound_id,
    compound_alias_id,
    compound_canonical_key,
)
from shared.identity import plant_compound_id
from shared.provenance import pubchem_compound_url, chembl_compound_url, knapsack_metabolite_url

import argparse
import csv
import hashlib
import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


CANDIDATE_COLUMNS = [
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

CANDIDATE_MEMBER_COLUMNS = [
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

ENRICH_RESULT_COLUMNS = [
    "compound_candidate_id",
    "candidate_key",
    "candidate_status",
    "search_priority",
    "search_terms_json",
    "pubchem_cid",
    "chembl_id",
    "inchi_key",
    "smiles",
    "molecular_formula",
    "molecular_weight",
    "iupac_name",
    "preferred_name",
    "source_name",
    "source_url",
    "source_batch_id",
    "retrieved_at",
    "enrichment_confidence",
    "enrichment_status",
    "match_strategy",
    "match_reason",
    "match_rank",
    "match_count",
    "cache_hit",
    "cache_key",
    "review_reason",
    "lipinski_source",
    "is_pains_positive",
]

ENRICH_MEMBER_MAP_COLUMNS = [
    "compound_candidate_member_id",
    "compound_candidate_id",
    "source_row_hash",
    "source_compound_key",
    "plant_id",
    "canonical_plant_id",
    "c_id",
    "cas_id",
    "metabolite",
    "normalized_metabolite_name",
    "normalized_metabolite_key",
    "normalized_cas_id",
    "normalized_cas_key",
    "normalized_formula",
    "normalized_formula_key",
    "normalization_status",
    "review_reason",
    "chosen_pubchem_cid",
    "chosen_chembl_id",
    "chosen_inchi_key",
    "chosen_smiles",
    "member_enrichment_status",
    "member_confidence",
]

ENRICH_REVIEW_COLUMNS = [
    "compound_candidate_id",
    "candidate_key",
    "candidate_status",
    "candidate_confidence",
    "match_strategy",
    "match_reason",
    "match_rank",
    "match_count",
    "representative_name",
    "representative_cas_id",
    "representative_formula",
    "representative_mw",
    "review_reason",
    "source_name",
    "source_batch_id",
    "retrieved_at",
    "evidence_summary_json",
]

COMPOUNDS_COLUMNS = [
    "compound_id",
    "canonical_key",
    "canonical_name",
    "inchi_key",
    "smiles",
    "cas_id",
    "pubchem_cid",
    "chembl_id",
    "molecular_formula",
    "molecular_weight",
    "tpsa",
    "logp",
    "hbond_donors",
    "hbond_acceptors",
    "rotatable_bonds",
    "qed_score",
    "np_likeness_score",
    "num_ro5_violations",
    "lipinski_source",
    "is_pains_positive",
    "source_name",
    "source_url",
    "retrieved_at",
    "canonical_status",
    "canonical_strategy",
    "canonical_reason",
    "evidence_count",
    "plant_count",
]

ALIASES_COLUMNS = [
    "compound_alias_id",
    "compound_id",
    "alias_name",
    "alias_key",
    "alias_type",
    "source_name",
    "source_url",
    "retrieved_at",
]

PLANT_COMPOUNDS_COLUMNS = [
    "plant_compound_id",
    "plant_id",
    "compound_id",
    "source_name",
    "source_url",
    "retrieved_at",
]

REVIEW_COLUMNS = [
    "compound_review_id",
    "compound_candidate_id",
    "compound_id",
    "candidate_key",
    "candidate_status",
    "enrichment_status",
    "canonical_status",
    "canonical_strategy",
    "canonical_reason",
    "representative_name",
    "representative_cas_id",
    "representative_formula",
    "representative_mw",
    "pubchem_cid",
    "chembl_id",
    "inchi_key",
    "smiles",
    "molecular_formula",
    "molecular_weight",
    "plant_id",
    "canonical_plant_id",
    "source_compound_key",
    "source_plant_raw_id",
    "source_name",
    "source_batch_id",
    "retrieved_at",
    "issue_type",
    "issue_reason",
    "evidence_summary_json",
]

CANDIDATE_MAP_COLUMNS = [
    "compound_candidate_map_id",
    "compound_candidate_id",
    "compound_id",
    "canonical_key",
    "canonical_status",
    "candidate_status",
    "enrichment_status",
    "decision_reason",
    "confidence",
    "source_name",
    "source_batch_id",
    "retrieved_at",
]

PLANT_REVIEW_COLUMNS = [
    "plant_compound_review_id",
    "compound_candidate_id",
    "compound_id",
    "canonical_key",
    "candidate_status",
    "enrichment_status",
    "plant_id",
    "canonical_plant_id",
    "source_compound_key",
    "source_plant_raw_id",
    "source_name",
    "source_batch_id",
    "retrieved_at",
    "issue_type",
    "issue_reason",
    "evidence_summary_json",
]

MAX_ALIASES_PER_COMPOUND = 32
MAX_SYNONYMS_PER_COMPOUND = 10
MAX_LIST_PREVIEW = 10


@dataclass(frozen=True)
class Settings:
    module_root: Path
    build_out_dir: Path
    build_log_dir: Path
    enrich_out_dir: Path
    dedupe_out_dir: Path
    candidate_input_file: Path
    candidate_members_file: Path
    enrich_results_file: Path
    enrich_member_map_file: Path
    enrich_review_file: Path
    enrich_cache_index_file: Path
    source_name: str
    source_url: str
    batch_id: str
    run_id_prefix: str
    timestamp_format: str
    overwrite_outputs: bool
    auto_accept_confidence: float
    high_confidence_threshold: float
    medium_confidence_threshold: float


# normalize_whitespace imported from shared.utils

def normalize_key(value: Optional[str]) -> str:
    text = normalize_whitespace(value).strip().lower()
    if not text:
        return ""
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def normalize_cas(value: Optional[str]) -> str:
    text = normalize_whitespace(value)
    if not text:
        return ""
    text = text.replace(" ", "")
    m = re.fullmatch(r"(\d{1,7})-?(\d{2})-?(\d)", text)
    if m:
        return f"{int(m.group(1))}-{m.group(2)}-{m.group(3)}"
    return text


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


def stable_hash(payload: Dict[str, Any]) -> str:
    canonical_json = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def stable_run_id(settings: Settings) -> str:
    if settings.batch_id and settings.batch_id != "auto":
        return f"{settings.run_id_prefix}_{settings.batch_id}"
    return f"{settings.run_id_prefix}_{datetime.now(timezone.utc).strftime(settings.timestamp_format)}"


def configure_logging(log_dir: Path, run_id: str) -> Path:
    ensure_dir(log_dir)
    log_path = log_dir / f"build_canonical_compounds_{run_id}.log"

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.handlers.clear()

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    root.addHandler(stream_handler)
    root.addHandler(file_handler)
    return log_path


def load_settings_for_build() -> Settings:
    config = shared_load_settings("compounds")

    paths_cfg = config.get("paths", {})
    step_dirs_cfg = paths_cfg.get("step_dirs", {})
    source_cfg = config.get("source", {})
    matching_cfg = config.get("matching", {})
    validation_cfg = config.get("validation", {})
    thresholds_cfg = validation_cfg.get("thresholds", {})

    build_out_dir = ETL_ROOT / step_dirs_cfg["build_canonical_out"]
    build_log_dir = build_out_dir / "logs"
    enrich_out_dir = ETL_ROOT / step_dirs_cfg["enrich_out"]
    dedupe_out_dir = ETL_ROOT / step_dirs_cfg["dedupe_candidates_out"]

    return Settings(
        module_root=ETL_ROOT / "compounds",
        build_out_dir=build_out_dir,
        build_log_dir=build_log_dir,
        enrich_out_dir=enrich_out_dir,
        dedupe_out_dir=dedupe_out_dir,
        candidate_input_file=dedupe_out_dir / "compound_candidates.csv",
        candidate_members_file=dedupe_out_dir / "compound_candidate_members.csv",
        enrich_results_file=enrich_out_dir / "compound_enrichment_results.csv",
        enrich_member_map_file=enrich_out_dir / "compound_enrichment_member_map.csv",
        enrich_review_file=enrich_out_dir / "compound_enrichment_review.csv",
        enrich_cache_index_file=enrich_out_dir / "compound_enrichment_cache.csv",
        source_name=str(source_cfg.get("name", "KNApSAcK")),
        source_url=str(source_cfg.get("url", "")),
        batch_id=str(source_cfg.get("batch_id", "auto")),
        run_id_prefix="compounds",
        timestamp_format="%Y%m%d_%H%M%S",
        overwrite_outputs=False,
        auto_accept_confidence=float(
            thresholds_cfg.get("min_compound_confidence_to_auto_accept", 0.70)
        ),
        high_confidence_threshold=float(
            matching_cfg.get("high_confidence_threshold", 0.90)
        ),
        medium_confidence_threshold=float(
            matching_cfg.get("medium_confidence_threshold", 0.70)
        ),
    )


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


def _write_csv_local(
    path: Path, rows: List[Dict[str, Any]], fieldnames: Sequence[str]
) -> None:
    ensure_dir(path.parent)
    path.unlink(missing_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_json_local(path: Path, payload: Dict[str, Any]) -> None:
    ensure_dir(path.parent)
    path.unlink(missing_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def safe_load_json(
    path: Path, logger: Optional[logging.Logger] = None
) -> Optional[Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        if logger is not None:
            logger.warning("Unable to read JSON file %s: %s", path, exc)
        return None


def load_enrichment_cache_payloads(
    cache_index_file: Path, logger: logging.Logger
) -> Dict[str, Dict[str, Any]]:
    if not cache_index_file.exists():
        return {}
    rows, fields = read_csv_rows(cache_index_file)
    if "compound_candidate_id" not in fields or "cache_file" not in fields:
        return {}
    payloads: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        cid = normalize_whitespace(row.get("compound_candidate_id", ""))
        cache_file = normalize_whitespace(row.get("cache_file", ""))
        if not cid or not cache_file:
            continue
        payload = safe_load_json(Path(cache_file), logger)
        if isinstance(payload, dict):
            payloads[cid] = payload
    logger.info("Loaded %d enrichment cache payloads", len(payloads))
    return payloads


def load_candidate_members(path: Path) -> List[Dict[str, str]]:
    rows, fields = read_csv_rows(path)
    ensure_columns(
        rows[0].keys() if rows else fields,
        CANDIDATE_MEMBER_COLUMNS,
        "compound_candidate_members.csv",
    )
    return rows


def load_enrichment_results(path: Path) -> List[Dict[str, str]]:
    rows, fields = read_csv_rows(path)
    ensure_columns(fields, ENRICH_RESULT_COLUMNS, "compound_enrichment_results.csv")
    return rows


def load_enrichment_member_map(path: Path) -> List[Dict[str, str]]:
    rows, fields = read_csv_rows(path)
    ensure_columns(
        fields, ENRICH_MEMBER_MAP_COLUMNS, "compound_enrichment_member_map.csv"
    )
    return rows


def load_enrichment_review(path: Path) -> List[Dict[str, str]]:
    rows, fields = read_csv_rows(path)
    ensure_columns(fields, ENRICH_REVIEW_COLUMNS, "compound_enrichment_review.csv")
    return rows


def group_by_candidate_id(
    rows: List[Dict[str, str]], key: str = "compound_candidate_id"
) -> Dict[str, List[Dict[str, str]]]:
    grouped: Dict[str, List[Dict[str, str]]] = defaultdict(list)
    for row in rows:
        cid = normalize_whitespace(row.get(key, ""))
        if cid:
            grouped[cid].append(row)
    return grouped


def build_candidate_member_join(
    candidate_members: List[Dict[str, str]],
    enrich_member_map: List[Dict[str, str]],
) -> Dict[str, List[Dict[str, Any]]]:
    map_by_member_id: Dict[str, Dict[str, str]] = {
        normalize_whitespace(r.get("compound_candidate_member_id", "")): r
        for r in enrich_member_map
        if normalize_whitespace(r.get("compound_candidate_member_id", ""))
    }
    grouped: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in candidate_members:
        member_id = normalize_whitespace(row.get("compound_candidate_member_id", ""))
        cid = normalize_whitespace(row.get("compound_candidate_id", ""))
        if not cid:
            continue
        enriched = map_by_member_id.get(member_id, {})
        merged = dict(row)
        merged.update(
            {
                k: v
                for k, v in enriched.items()
                if k not in merged or not normalize_whitespace(merged.get(k, ""))
            }
        )
        grouped[cid].append(merged)
    return grouped


def make_bridge_id(plant_id: str, compound_id: str) -> str:
    return plant_compound_id(plant_id, compound_id)


def make_review_id(seed: str) -> str:
    return f"cmprev_{hashlib.sha256(seed.encode('utf-8')).hexdigest()[:16]}"


def most_common_nonempty(values: Iterable[str]) -> str:
    cleaned = [normalize_whitespace(v) for v in values if normalize_whitespace(v)]
    if not cleaned:
        return ""
    return Counter(cleaned).most_common(1)[0][0]


def canonical_identity_for_candidate(candidate: Dict[str, str]) -> Tuple[str, str]:
    key = compound_canonical_key(candidate)
    prefix = key.split(":", 1)[0] if key else ""
    strategy = {
        "inchikey": "inchi_key",
        "pubchem": "pubchem_cid",
        "chembl": "chembl_id",
        "cas": "cas_id",
        "name_formula": "name_formula",
        "name": "name",
        "formula": "formula",
    }.get(prefix, prefix)
    return key, strategy


def candidate_name(
    candidate: Dict[str, str], member_rows: List[Dict[str, Any]], canonical_key: str
) -> str:
    best = normalize_whitespace(
        candidate.get("preferred_name")
        or candidate.get("iupac_name")
        or candidate.get("representative_name", "")
    )
    if best:
        return best
    member_name = most_common_nonempty(
        r.get("normalized_metabolite_name") or r.get("metabolite") or ""
        for r in member_rows
    )
    if member_name:
        return member_name
    return canonical_key


def candidate_cas(candidate: Dict[str, str], member_rows: List[Dict[str, Any]]) -> str:
    best = normalize_cas(candidate.get("representative_cas_id", ""))
    if best:
        return best
    return most_common_nonempty(
        r.get("normalized_cas_id") or r.get("cas_id") or "" for r in member_rows
    )


def candidate_formula(
    candidate: Dict[str, str], member_rows: List[Dict[str, Any]]
) -> str:
    best = normalize_whitespace(
        candidate.get("molecular_formula")
        or candidate.get("representative_formula", "")
    )
    if best:
        return best
    return most_common_nonempty(
        r.get("normalized_formula") or r.get("molecular_formula") or ""
        for r in member_rows
    )


def candidate_weight(
    candidate: Dict[str, str], member_rows: List[Dict[str, Any]]
) -> str:
    best = normalize_whitespace(
        candidate.get("molecular_weight") or candidate.get("representative_mw", "")
    )
    if best:
        return best
    return most_common_nonempty(
        r.get("normalized_mw") or r.get("mw") or "" for r in member_rows
    )


def candidate_smiles(candidate: Dict[str, str]) -> str:
    return normalize_whitespace(candidate.get("smiles", ""))


def candidate_inchi(candidate: Dict[str, str]) -> str:
    return normalize_whitespace(candidate.get("inchi_key", ""))


def candidate_pubchem(candidate: Dict[str, str]) -> str:
    return normalize_whitespace(candidate.get("pubchem_cid", ""))


def candidate_chembl(candidate: Dict[str, str]) -> str:
    return normalize_whitespace(candidate.get("chembl_id", ""))


def unique_nonempty(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen: set[str] = set()
    for v in values:
        s = normalize_whitespace(v)
        if not s:
            continue
        key = normalize_key(s)
        if key in seen:
            continue
        seen.add(key)
        out.append(s)
    return out


def support_profile(
    candidate: Dict[str, str], member_rows: List[Dict[str, Any]]
) -> Tuple[float, str]:
    enr_status = normalize_whitespace(candidate.get("enrichment_status", "")).lower()
    conf = parse_float(candidate.get("enrichment_confidence", "")) or 0.0

    inchi = candidate_inchi(candidate)
    pubchem_cid = candidate_pubchem(candidate)
    chembl_id = candidate_chembl(candidate)
    cas_id = candidate_cas(candidate, member_rows)
    name = candidate_name(
        candidate,
        member_rows,
        (
            ""
            if not candidate.get("preferred_name")
            else normalize_key(candidate.get("preferred_name"))
        ),
    )
    formula = candidate_formula(candidate, member_rows)
    mw = candidate_weight(candidate, member_rows)

    unique_names = unique_nonempty(
        (r.get("normalized_metabolite_name") or r.get("metabolite") or "")
        for r in member_rows
    )
    unique_cas = unique_nonempty(
        (r.get("normalized_cas_id") or r.get("cas_id") or "") for r in member_rows
    )
    unique_forms = unique_nonempty(
        (r.get("normalized_formula") or r.get("molecular_formula") or "")
        for r in member_rows
    )

    score = 0.0
    reasons: List[str] = []

    if inchi:
        score += 0.55
        reasons.append("inchi_key")
    elif pubchem_cid and chembl_id:
        score += 0.50
        reasons.append("pubchem_and_chembl")
    elif pubchem_cid:
        score += 0.46
        reasons.append("pubchem_cid")
    elif chembl_id:
        score += 0.46
        reasons.append("chembl_id")
    elif cas_id and name and formula:
        score += 0.40
        reasons.append("cas_name_formula")
    elif cas_id:
        score += 0.30
        reasons.append("cas_id")
    elif name and formula:
        score += 0.28
        reasons.append("name_formula")
    elif name:
        score += 0.20
        reasons.append("name")
    elif formula:
        score += 0.14
        reasons.append("formula")
    else:
        score += 0.05
        reasons.append("weak_identity")

    if len(member_rows) > 1:
        bonus = min(0.10, 0.02 * (len(member_rows) - 1))
        score += bonus
        reasons.append(f"member_support_{bonus:.2f}")

    if len(unique_names) >= 2:
        bonus = min(0.10, 0.03 * (len(unique_names) - 1))
        score += bonus
        reasons.append(f"name_consensus_{bonus:.2f}")

    if len(unique_cas) >= 2:
        bonus = min(0.08, 0.02 * (len(unique_cas) - 1))
        score += bonus
        reasons.append(f"cas_consensus_{bonus:.2f}")

    if len(unique_forms) >= 2:
        bonus = min(0.05, 0.02 * (len(unique_forms) - 1))
        score += bonus
        reasons.append(f"formula_consensus_{bonus:.2f}")

    if inchi and pubchem_cid and chembl_id:
        score += 0.10
        reasons.append("cross_source_agreement")

    if enr_status == "matched":
        score += 0.05
        reasons.append("matched_status")
    elif enr_status in {"ambiguous", "conflict"}:
        score -= 0.03
        reasons.append("salvage_penalty")

    score = max(0.0, min(1.0, score))
    return score, ";".join(reasons)


def decide_canonical_status(
    candidate: Dict[str, str], member_rows: List[Dict[str, Any]], settings: Settings
) -> Dict[str, Any]:
    enr_status = normalize_whitespace(candidate.get("enrichment_status", "")).lower()
    conf = parse_float(candidate.get("enrichment_confidence", "")) or 0.0
    canonical_key, canonical_strategy = canonical_identity_for_candidate(candidate)
    score, score_reason = support_profile(candidate, member_rows)

    strong_identity = canonical_strategy in {"inchi_key", "pubchem_cid", "chembl_id"}
    medium_identity = canonical_strategy in {"cas_id", "name_formula"}
    weak_identity = canonical_strategy in {"name", "formula"}
    source_priority = f"{enr_status}:{canonical_strategy}"

    canonical_status = "review"
    canonical_reason = "insufficient_identity_support"

    if not canonical_key:
        canonical_status = "unresolved"
        canonical_reason = "missing_canonical_key"
    else:
        if (
            strong_identity
            and conf >= max(settings.high_confidence_threshold, 0.80)
            and score >= 0.55
        ):
            canonical_status = "accepted"
            canonical_reason = "strong_identity_high_confidence"
        elif strong_identity and conf >= 0.55 and score >= 0.45:
            canonical_status = "provisional"
            canonical_reason = f"{enr_status}_strong_identity_salvage"
        elif (
            medium_identity
            and conf >= settings.medium_confidence_threshold
            and score >= 0.55
        ):
            canonical_status = "provisional"
            canonical_reason = f"{enr_status}_supportive_chemistry"
        elif weak_identity and conf >= 0.80 and score >= 0.72:
            canonical_status = "provisional"
            canonical_reason = f"{enr_status}_weak_identity_but_consistent"
        elif (
            enr_status in {"ambiguous", "conflict"}
            and score >= 0.42
            and (strong_identity or medium_identity)
        ):
            canonical_status = "provisional"
            canonical_reason = f"{enr_status}_deterministic_salvage"
        elif (
            enr_status == "review"
            and score >= 0.45
            and (strong_identity or medium_identity)
        ):
            canonical_status = "provisional"
            canonical_reason = "review_salvageable_identity"
        elif score < 0.30:
            canonical_status = "unresolved"
            canonical_reason = "too_weak_or_contradictory"
        else:
            canonical_status = "review"
            canonical_reason = f"{enr_status}_not_strong_enough"

    return {
        "canonical_key": canonical_key,
        "canonical_strategy": canonical_strategy,
        "canonical_status": canonical_status,
        "canonical_reason": canonical_reason,
        "confidence": conf,
        "support_score": score,
        "support_reason": score_reason,
        "enrichment_status": enr_status,
        "source_priority": source_priority,
    }


def best_candidate_entry(entries: List[Dict[str, Any]]) -> Dict[str, Any]:
    def rank(entry: Dict[str, Any]) -> Tuple[int, float, int, str]:
        status = entry["decision"]["canonical_status"]
        rank_map = {"accepted": 2, "provisional": 1, "review": 0, "unresolved": -1}
        return (
            rank_map.get(status, 0),
            entry["decision"]["confidence"],
            int(entry["candidate"].get("member_count", "0") or 0),
            normalize_whitespace(entry["candidate"].get("compound_candidate_id", "")),
        )

    return sorted(entries, key=rank, reverse=True)[0]


def group_status(entries: List[Dict[str, Any]], settings: Settings) -> str:
    if not entries:
        return "unresolved"

    statuses = [e["decision"]["canonical_status"] for e in entries]

    if any(s == "accepted" for s in statuses):
        return "accepted"
    if any(s == "provisional" for s in statuses):
        return "provisional"
    if any(s == "review" for s in statuses):
        return "review"
    return "unresolved"


def combined_group_reason(
    best_entry: Dict[str, Any], entries: List[Dict[str, Any]], group_status_value: str
) -> str:
    decision = best_entry["decision"]
    merged_note = f"group_size={len(entries)}"
    status_note = f"group_status={group_status_value}"
    return ";".join(
        [
            decision["canonical_reason"],
            decision["support_reason"],
            decision["source_priority"],
            merged_note,
            status_note,
            f"match_reason={normalize_whitespace(best_entry['candidate'].get('match_reason', ''))}",
        ]
    ).strip(";")


def collect_alias_items(
    compound_id: str,
    group_entries: List[Dict[str, Any]],
    best_entry: Dict[str, Any],
    canonical_name: str,
    source_url: str,
    retrieved_at: str,
) -> List[Dict[str, Any]]:
    items: List[Dict[str, Any]] = []

    def add(
        name: Optional[str],
        alias_type: str,
        source_name: str,
        url: str,
        priority: int,
    ) -> None:
        text = normalize_whitespace(name)
        if not text:
            return
        if len(text) < 2 or len(text) > 120:
            return

        alias_key = normalize_key(text)
        if not alias_key:
            return

        if alias_type == "enrichment_synonym":
            if re.fullmatch(r"[\d\W_]+", text):
                return

        if alias_key in {
            "compound",
            "unknown",
            "unidentified",
            "extract",
            "metabolite",
        } and alias_type not in {"cas_id", "source_compound_id"}:
            return

        items.append(
            {
                "alias_name": text,
                "alias_key": alias_key,
                "alias_type": alias_type,
                "source_name": source_name,
                "source_url": url,
                "retrieved_at": retrieved_at,
                "priority": priority,
            }
        )

    candidate = best_entry["candidate"]
    cache_payload = best_entry.get("cache_payload") or {}
    ordered_hits = (
        cache_payload.get("ordered_hits", []) if isinstance(cache_payload, dict) else []
    )
    best_hit = ordered_hits[0] if ordered_hits else {}

    add(
        canonical_name,
        "canonical_name",
        candidate.get("source_name", source_url),
        source_url,
        1,
    )
    add(
        candidate.get("preferred_name"),
        "preferred_name",
        candidate.get("source_name", source_url),
        source_url,
        2,
    )
    add(
        candidate.get("iupac_name"),
        "iupac_name",
        candidate.get("source_name", source_url),
        source_url,
        3,
    )
    add(
        candidate.get("representative_name"),
        "representative_name",
        candidate.get("source_name", source_url),
        source_url,
        4,
    )
    add(
        candidate.get("representative_cas_id"),
        "cas_id",
        candidate.get("source_name", source_url),
        source_url,
        5,
    )

    member_names = unique_nonempty(
        (r.get("normalized_metabolite_name") or r.get("metabolite") or "")
        for entry in group_entries
        for r in entry["members"]
    )
    member_cas = unique_nonempty(
        (r.get("normalized_cas_id") or r.get("cas_id") or "")
        for entry in group_entries
        for r in entry["members"]
    )
    member_source_ids = unique_nonempty(
        r.get("c_id") or "" for entry in group_entries for r in entry["members"]
    )

    for idx, name in enumerate(member_names[:6], start=10):
        add(
            name,
            "raw_metabolite_name",
            best_entry["candidate"].get("source_name", source_url),
            source_url,
            idx,
        )

    for idx, cid in enumerate(member_source_ids[:4], start=20):
        add(
            cid,
            "source_compound_id",
            best_entry["candidate"].get("source_name", source_url),
            source_url,
            idx,
        )

    for idx, cas in enumerate(member_cas[:6], start=30):
        add(
            normalize_cas(cas),
            "cas_id",
            best_entry["candidate"].get("source_name", source_url),
            source_url,
            idx,
        )

    synonyms: List[str] = []
    if isinstance(best_hit, dict):
        raw_syns = best_hit.get("synonyms", []) or []
        if isinstance(raw_syns, list):
            synonyms = unique_nonempty(raw_syns)[:MAX_SYNONYMS_PER_COMPOUND]

    for idx, syn in enumerate(synonyms, start=40):
        add(
            syn,
            "enrichment_synonym",
            best_hit.get("source_name", candidate.get("source_name", source_url)),
            best_hit.get("source_url", source_url),
            idx,
        )

    items.sort(
        key=lambda x: (x["priority"], x["alias_key"], x["alias_type"], x["alias_name"])
    )

    out: List[Dict[str, Any]] = []
    seen_alias_keys: set[str] = set()
    for item in items:
        if len(out) >= MAX_ALIASES_PER_COMPOUND:
            break
        if item["alias_key"] in seen_alias_keys:
            continue
        seen_alias_keys.add(item["alias_key"])
        out.append(
            {
                "compound_alias_id": compound_alias_id(compound_id, item["alias_key"]),
                "compound_id": compound_id,
                "alias_name": item["alias_name"],
                "alias_key": item["alias_key"],
                "alias_type": item["alias_type"],
                "source_name": item["source_name"],
                "source_url": item["source_url"],
                "retrieved_at": item["retrieved_at"],
            }
        )
    return out


def build_candidate_review_row(
    candidate: Dict[str, str],
    decision: Dict[str, Any],
    member_rows: List[Dict[str, Any]],
    sidecar_rows: List[Dict[str, str]],
) -> Dict[str, Any]:
    unmapped_members = [
        m
        for m in member_rows
        if not normalize_whitespace(m.get("canonical_plant_id", ""))
    ]
    first_member = member_rows[0] if member_rows else {}
    sidecar_reason = ";".join(
        unique_nonempty(r.get("review_reason") or "" for r in sidecar_rows)
    )
    issue_reason = ";".join(
        unique_nonempty(
            [
                decision["canonical_reason"],
                normalize_whitespace(candidate.get("review_reason", "")),
                normalize_whitespace(candidate.get("match_reason", "")),
                sidecar_reason,
            ]
        )
    )

    return {
        "compound_review_id": make_review_id(
            f"{normalize_whitespace(candidate.get('compound_candidate_id', ''))}|{decision['canonical_status']}"
        ),
        "compound_candidate_id": normalize_whitespace(
            candidate.get("compound_candidate_id", "")
        ),
        "compound_id": "",
        "candidate_key": normalize_whitespace(candidate.get("candidate_key", "")),
        "candidate_status": normalize_whitespace(candidate.get("candidate_status", "")),
        "enrichment_status": normalize_whitespace(
            candidate.get("enrichment_status", "")
        ),
        "canonical_status": decision["canonical_status"],
        "canonical_strategy": decision["canonical_strategy"],
        "canonical_reason": decision["canonical_reason"],
        "representative_name": normalize_whitespace(
            candidate.get("preferred_name")
            or candidate.get("iupac_name")
            or candidate.get("representative_name", "")
        ),
        "representative_cas_id": normalize_whitespace(
            candidate.get("representative_cas_id", "")
        ),
        "representative_formula": normalize_whitespace(
            candidate.get("molecular_formula")
            or candidate.get("representative_formula", "")
        ),
        "representative_mw": normalize_whitespace(
            candidate.get("molecular_weight") or candidate.get("representative_mw", "")
        ),
        "pubchem_cid": normalize_whitespace(candidate.get("pubchem_cid", "")),
        "chembl_id": normalize_whitespace(candidate.get("chembl_id", "")),
        "inchi_key": normalize_whitespace(candidate.get("inchi_key", "")),
        "smiles": normalize_whitespace(candidate.get("smiles", "")),
        "molecular_formula": normalize_whitespace(
            candidate.get("molecular_formula", "")
        ),
        "molecular_weight": normalize_whitespace(candidate.get("molecular_weight", "")),
        "plant_id": "",
        "canonical_plant_id": "",
        "source_compound_key": normalize_whitespace(
            first_member.get("source_compound_key", "")
        ),
        "source_plant_raw_id": normalize_whitespace(first_member.get("plant_id", "")),
        "source_name": normalize_whitespace(candidate.get("source_name", "")),
        "source_batch_id": normalize_whitespace(candidate.get("source_batch_id", "")),
        "retrieved_at": normalize_whitespace(candidate.get("retrieved_at", "")),
        "issue_type": decision["canonical_status"],
        "issue_reason": issue_reason,
        "evidence_summary_json": json.dumps(
            {
                "candidate_id": normalize_whitespace(
                    candidate.get("compound_candidate_id", "")
                ),
                "candidate_status": normalize_whitespace(
                    candidate.get("candidate_status", "")
                ),
                "enrichment_status": normalize_whitespace(
                    candidate.get("enrichment_status", "")
                ),
                "confidence": candidate.get("enrichment_confidence", ""),
                "support_score": decision["support_score"],
                "support_reason": decision["support_reason"],
                "member_count": len(member_rows),
                "mapped_member_count": sum(
                    1
                    for m in member_rows
                    if normalize_whitespace(m.get("canonical_plant_id", ""))
                ),
                "unmapped_member_count": len(unmapped_members),
                "review_sidecar_rows": len(sidecar_rows),
                "member_ids_preview": [
                    normalize_whitespace(m.get("compound_candidate_member_id", ""))
                    for m in member_rows[:MAX_LIST_PREVIEW]
                ],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def build_unmapped_review_row(
    best_entry: Dict[str, Any],
    group_entries: List[Dict[str, Any]],
    compound_id: str,
) -> Dict[str, Any]:
    candidate = best_entry["candidate"]
    member_rows = [
        m
        for entry in group_entries
        for m in entry["members"]
        if not normalize_whitespace(m.get("canonical_plant_id", ""))
    ]
    member_ids = unique_nonempty(
        m.get("compound_candidate_member_id") or "" for m in member_rows
    )
    raw_plants = unique_nonempty(
        m.get("plant_id") or m.get("raw_plant_key") or "" for m in member_rows
    )
    source_compound_keys = unique_nonempty(
        m.get("source_compound_key") or "" for m in member_rows
    )
    first_member = member_rows[0] if member_rows else {}

    return {
        "plant_compound_review_id": make_review_id(
            f"{normalize_whitespace(candidate.get('compound_candidate_id', ''))}|unmapped_plant_reference|{stable_hash({'member_ids': member_ids})}"
        ),
        "compound_candidate_id": normalize_whitespace(
            candidate.get("compound_candidate_id", "")
        ),
        "compound_id": compound_id,
        "canonical_key": normalize_whitespace(best_entry["decision"]["canonical_key"]),
        "candidate_status": normalize_whitespace(candidate.get("candidate_status", "")),
        "enrichment_status": normalize_whitespace(
            candidate.get("enrichment_status", "")
        ),
        "plant_id": normalize_whitespace(first_member.get("plant_id", "")),
        "canonical_plant_id": "",
        "source_compound_key": normalize_whitespace(
            first_member.get("source_compound_key", "")
        ),
        "source_plant_raw_id": ";".join(raw_plants[:MAX_LIST_PREVIEW]),
        "source_name": normalize_whitespace(candidate.get("source_name", "")),
        "source_batch_id": normalize_whitespace(candidate.get("source_batch_id", "")),
        "retrieved_at": normalize_whitespace(candidate.get("retrieved_at", "")),
        "issue_type": "unmapped_plant_reference",
        "issue_reason": "member_map_missing_canonical_plant_id",
        "evidence_summary_json": json.dumps(
            {
                "candidate_id": normalize_whitespace(
                    candidate.get("compound_candidate_id", "")
                ),
                "compound_id": compound_id,
                "member_count": len(member_rows),
                "missing_member_count": len(member_rows),
                "member_ids_preview": member_ids[:MAX_LIST_PREVIEW],
                "source_compound_keys_preview": source_compound_keys[:MAX_LIST_PREVIEW],
                "raw_plant_ids_preview": raw_plants[:MAX_LIST_PREVIEW],
            },
            ensure_ascii=False,
            sort_keys=True,
        ),
    }


def build_canonical_tables(
    settings: Settings,
    logger: logging.Logger,
) -> Tuple[
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    List[Dict[str, Any]],
    Dict[str, Any],
]:
    candidate_rows = load_enrichment_results(settings.enrich_results_file)
    candidate_members = load_candidate_members(settings.candidate_members_file)
    enrich_member_map = load_enrichment_member_map(settings.enrich_member_map_file)
    enrich_review_rows = load_enrichment_review(settings.enrich_review_file)
    cache_payloads = load_enrichment_cache_payloads(
        settings.enrich_cache_index_file, logger
    )

    candidate_members_by_candidate = build_candidate_member_join(
        candidate_members, enrich_member_map
    )
    review_by_candidate = group_by_candidate_id(enrich_review_rows)

    decision_counts = Counter()
    review_entries: Dict[Tuple[str, str], Dict[str, Any]] = {}

    candidate_map_index: Dict[str, Dict[str, Any]] = {}

    compound_review_entries: Dict[Tuple[str, str], Dict[str, Any]] = {}
    plant_review_entries: Dict[Tuple[str, str], Dict[str, Any]] = {}
    candidate_groups: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

    for candidate in candidate_rows:
        cid = normalize_whitespace(candidate.get("compound_candidate_id", ""))
        if not cid:
            continue

        member_rows = candidate_members_by_candidate.get(cid, [])
        sidecar_rows = review_by_candidate.get(cid, [])
        decision = decide_canonical_status(candidate, member_rows, settings)
        decision_counts[decision["canonical_status"]] += 1

        entry = {
            "candidate": candidate,
            "members": member_rows,
            "decision": decision,
            "cache_payload": cache_payloads.get(cid, {}),
            "sidecar_rows": sidecar_rows,
        }

        candidate_map_index[cid] = {
            "compound_candidate_map_id": f"cmpmap_{stable_hash({'candidate_id': cid, 'canonical_key': decision['canonical_key']})[:16]}",
            "compound_candidate_id": cid,
            "compound_id": "",
            "canonical_key": decision["canonical_key"],
            "canonical_status": decision["canonical_status"],
            "candidate_status": normalize_whitespace(
                candidate.get("candidate_status", "")
            ),
            "enrichment_status": decision["enrichment_status"],
            "decision_reason": decision["canonical_reason"],
            "confidence": f"{decision['confidence']:.4f}",
            "source_name": normalize_whitespace(
                candidate.get("source_name", settings.source_name)
            ),
            "source_batch_id": normalize_whitespace(
                candidate.get("source_batch_id", settings.batch_id)
            ),
            "retrieved_at": normalize_whitespace(
                candidate.get("retrieved_at", timestamp_now())
            )
            or timestamp_now(),
        }

        if decision["canonical_status"] in {"accepted", "provisional"}:
            candidate_groups[decision["canonical_key"]].append(entry)
        else:
            review_row = build_candidate_review_row(
                candidate, decision, member_rows, sidecar_rows
            )
            compound_review_entries[(cid, "candidate")] = review_row

    compounds_out: List[Dict[str, Any]] = []
    aliases_out: List[Dict[str, Any]] = []
    bridge_out: List[Dict[str, Any]] = []
    bridge_seen: set[Tuple[str, str]] = set()

    for canonical_key in sorted(candidate_groups.keys()):
        entries = candidate_groups[canonical_key]
        entries_sorted = sorted(
            entries,
            key=lambda e: (
                {"accepted": 2, "provisional": 1}.get(
                    e["decision"]["canonical_status"], 0
                ),
                e["decision"]["confidence"],
                int(e["candidate"].get("member_count", "0") or 0),
                normalize_whitespace(e["candidate"].get("compound_candidate_id", "")),
            ),
            reverse=True,
        )
        best_entry = entries_sorted[0]
        best_candidate = best_entry["candidate"]
        group_members = [m for entry in entries_sorted for m in entry["members"]]
        selected_status = group_status(entries_sorted, settings)
        compound_id = make_compound_id(canonical_key)

        canonical_name = candidate_name(best_candidate, group_members, canonical_key)
        cas_id = candidate_cas(best_candidate, group_members)
        formula = candidate_formula(best_candidate, group_members)
        mw = candidate_weight(best_candidate, group_members)
        tpsa = normalize_whitespace(best_candidate.get("tpsa", ""))
        logp = normalize_whitespace(best_candidate.get("logp", ""))
        hbond_donors = normalize_whitespace(best_candidate.get("hbond_donors", ""))
        hbond_acceptors = normalize_whitespace(best_candidate.get("hbond_acceptors", ""))
        rotatable_bonds = normalize_whitespace(best_candidate.get("rotatable_bonds", ""))
        qed_score = normalize_whitespace(best_candidate.get("qed_score", ""))
        np_likeness_score = normalize_whitespace(best_candidate.get("np_likeness_score", ""))
        num_ro5_violations = normalize_whitespace(best_candidate.get("num_ro5_violations", ""))
        lipinski_source = normalize_whitespace(best_candidate.get("lipinski_source", ""))
        is_pains_positive = normalize_whitespace(best_candidate.get("is_pains_positive", ""))
        inchi_key = candidate_inchi(best_candidate)
        smiles = candidate_smiles(best_candidate)
        pubchem_cid = candidate_pubchem(best_candidate)
        chembl_id = candidate_chembl(best_candidate)

        source_name = normalize_whitespace(
            best_candidate.get("source_name", settings.source_name)
        )
        source_url = (
            pubchem_compound_url(pubchem_cid)
            or chembl_compound_url(chembl_id)
            or normalize_whitespace(best_candidate.get("source_url", settings.source_url))
        )
        source_batch_id = normalize_whitespace(
            best_candidate.get("source_batch_id", settings.batch_id)
        )
        retrieved_at = (
            normalize_whitespace(best_candidate.get("retrieved_at", timestamp_now()))
            or timestamp_now()
        )
        best_conf = max(e["decision"]["confidence"] for e in entries_sorted)

        for entry in entries_sorted:
            cid = normalize_whitespace(
                entry["candidate"].get("compound_candidate_id", "")
            )
            if cid and cid in candidate_map_index:
                candidate_map_index[cid].update(
                    {
                        "compound_id": compound_id,
                        "canonical_key": canonical_key,
                        "canonical_status": selected_status,
                        "decision_reason": combined_group_reason(
                            best_entry, entries_sorted, selected_status
                        ),
                        "confidence": f"{best_conf:.4f}",
                        "source_name": source_name,
                        "source_batch_id": source_batch_id,
                        "retrieved_at": retrieved_at,
                    }
                )

        evidence_count = len(group_members)
        mapped_plants = unique_nonempty(
            m.get("canonical_plant_id") or ""
            for m in group_members
            if normalize_whitespace(m.get("canonical_plant_id", ""))
        )
        plant_count = len(mapped_plants)

        compounds_out.append(
            {
                "compound_id": compound_id,
                "canonical_key": canonical_key,
                "canonical_name": canonical_name,
                "inchi_key": inchi_key,
                "smiles": smiles,
                "cas_id": cas_id,
                "pubchem_cid": pubchem_cid,
                "chembl_id": chembl_id,
                "molecular_formula": formula,
                "molecular_weight": mw,
                "tpsa": tpsa,
                "logp": logp,
                "hbond_donors": hbond_donors,
                "hbond_acceptors": hbond_acceptors,
                "rotatable_bonds": rotatable_bonds,
                "qed_score": qed_score,
                "np_likeness_score": np_likeness_score,
                "num_ro5_violations": num_ro5_violations,
                "lipinski_source": lipinski_source,
                "is_pains_positive": is_pains_positive,
                "source_name": source_name,
                "source_url": source_url,
                "retrieved_at": retrieved_at,
                "canonical_status": selected_status,
                "canonical_strategy": best_entry["decision"]["canonical_strategy"],
                "canonical_reason": combined_group_reason(
                    best_entry, entries_sorted, selected_status
                ),
                "evidence_count": str(evidence_count),
                "plant_count": str(plant_count),
            }
        )

        aliases_out.extend(
            collect_alias_items(
                compound_id=compound_id,
                group_entries=entries_sorted,
                best_entry=best_entry,
                canonical_name=canonical_name,
                source_url=source_url,
                retrieved_at=retrieved_at,
            )
        )

        unmapped_member_rows = [
            m
            for m in group_members
            if not normalize_whitespace(m.get("canonical_plant_id", ""))
        ]
        if unmapped_member_rows:
            plant_review_row = build_unmapped_review_row(
                best_entry, entries_sorted, compound_id
            )
            plant_review_entries[
                (
                    normalize_whitespace(
                        best_candidate.get("compound_candidate_id", "")
                    ),
                    "unmapped_plant_reference",
                )
            ] = plant_review_row

        for member in group_members:
            canonical_plant_id = normalize_whitespace(
                member.get("canonical_plant_id", "")
            )
            if not canonical_plant_id:
                continue
            raw_compound_id = normalize_whitespace(member.get("c_id", ""))
            bridge_key = (canonical_plant_id, compound_id)
            if bridge_key in bridge_seen:
                continue
            bridge_seen.add(bridge_key)
            bridge_out.append(
                {
                    "plant_compound_id": make_bridge_id(
                        canonical_plant_id, compound_id
                    ),
                    "plant_id": canonical_plant_id,
                    "compound_id": compound_id,
                    "source_name": normalize_whitespace(
                        member.get("source_name", source_name)
                    ),
                    "source_url": (
                        knapsack_metabolite_url(raw_compound_id)
                        or normalize_whitespace(member.get("source_url", settings.source_url))
                    ),
                    "retrieved_at": normalize_whitespace(
                        member.get("retrieved_at", retrieved_at)
                    )
                    or retrieved_at,
                }
            )

    # Deduplicate aliases more aggressively by alias_key only (first best provenance wins)
    aliases_deduped: List[Dict[str, Any]] = []
    alias_seen: set[Tuple[str, str]] = set()
    for row in sorted(
        aliases_out,
        key=lambda r: (
            r["compound_id"],
            r["alias_key"],
            r["alias_type"],
            r["alias_name"],
        ),
    ):
        key = (row["compound_id"], row["alias_key"])
        if key in alias_seen:
            continue
        alias_seen.add(key)
        aliases_deduped.append(
            {
                "compound_alias_id": compound_alias_id(row["compound_id"], row["alias_key"]),
                "compound_id": row["compound_id"],
                "alias_name": row["alias_name"],
                "alias_key": row["alias_key"],
                "alias_type": row["alias_type"],
                "source_name": row["source_name"],
                "source_url": row["source_url"],
                "retrieved_at": row["retrieved_at"],
            }
        )

    compounds_out = sorted(
        compounds_out, key=lambda r: (r["canonical_key"], r["compound_id"])
    )
    aliases_out = sorted(
        aliases_deduped,
        key=lambda r: (r["compound_id"], r["alias_key"], r["alias_type"]),
    )
    bridge_out = sorted(
        bridge_out,
        key=lambda r: (r["plant_id"], r["compound_id"], r["plant_compound_id"]),
    )
    compound_review_rows_out = sorted(
        compound_review_entries.values(),
        key=lambda r: (
            r["compound_candidate_id"],
            r["issue_type"],
            r["compound_review_id"],
        ),
    )
    plant_review_rows_out = sorted(
        plant_review_entries.values(),
        key=lambda r: (
            r["compound_candidate_id"],
            r["issue_type"],
            r["plant_compound_review_id"],
        ),
    )

    candidate_map_out = sorted(
        candidate_map_index.values(),
        key=lambda r: (
            r["canonical_key"],
            r["compound_id"],
            r["compound_candidate_id"],
        ),
    )

    summary = {
        "module": "compounds",
        "step": "05_build_canonical",
        "run_id": stable_run_id(settings),
        "settings_file": str(settings.module_root / "settings.yml"),
        "enrich_results_file": str(settings.enrich_results_file),
        "enrich_member_map_file": str(settings.enrich_member_map_file),
        "enrich_review_file": str(settings.enrich_review_file),
        "candidate_input_file": str(settings.candidate_input_file),
        "candidate_members_file": str(settings.candidate_members_file),
        "output_compounds_file": str(settings.build_out_dir / "compounds.csv"),
        "output_aliases_file": str(settings.build_out_dir / "compound_aliases.csv"),
        "output_bridge_file": str(settings.build_out_dir / "plant_compounds.csv"),
        "output_review_file": str(settings.build_out_dir / "compound_review.csv"),
        "output_candidate_map_file": str(
            settings.build_out_dir / "compound_candidate_map.csv"
        ),
        "candidate_rows": len(candidate_rows),
        "candidate_member_rows": len(candidate_members),
        "accepted_candidate_count": decision_counts["accepted"],
        "provisional_candidate_count": decision_counts["provisional"],
        "review_candidate_count": decision_counts["review"],
        "unresolved_candidate_count": decision_counts["unresolved"],
        "canonical_compound_count": len(compounds_out),
        "accepted_compounds": sum(
            1 for r in compounds_out if r["canonical_status"] == "accepted"
        ),
        "provisional_compounds": sum(
            1 for r in compounds_out if r["canonical_status"] == "provisional"
        ),
        "candidate_map_row_count": len(candidate_map_out),
        "alias_row_count": len(aliases_out),
        "plant_compound_row_count": len(bridge_out),
        "merged_group_count": sum(
            1 for r in compounds_out if int(r["evidence_count"]) > 1
        ),
        "compound_review_row_count": len(compound_review_rows_out),
        "plant_review_row_count": len(plant_review_rows_out),
        "unmapped_plant_rows": len(plant_review_rows_out),
        "generated_at": timestamp_now(),
    }

    return (
        compounds_out,
        aliases_out,
        bridge_out,
        compound_review_rows_out,
        plant_review_rows_out,
        candidate_map_out,
        summary,
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Build canonical compound seed tables."
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to the compound ETL settings.yml file.",
    )
    args = parser.parse_args()

    settings = load_settings_for_build()
    run_id = make_run_id("compounds")
    log_path = configure_logging(settings.build_log_dir, run_id)
    logger = logging.getLogger("compounds.build_canonical")

    logger.info("Starting canonical build run_id=%s", run_id)
    logger.info("Settings path: %s", args.settings)
    logger.info("Enrichment results: %s", settings.enrich_results_file)
    logger.info("Enrichment member map: %s", settings.enrich_member_map_file)
    logger.info("Enrichment review: %s", settings.enrich_review_file)
    logger.info("Candidate input: %s", settings.candidate_input_file)
    logger.info("Candidate members: %s", settings.candidate_members_file)

    if not settings.enrich_results_file.exists():
        raise FileNotFoundError(
            f"Enrichment results file not found: {settings.enrich_results_file}"
        )
    if not settings.enrich_member_map_file.exists():
        raise FileNotFoundError(
            f"Enrichment member map file not found: {settings.enrich_member_map_file}"
        )
    if not settings.candidate_input_file.exists():
        raise FileNotFoundError(
            f"Candidate input file not found: {settings.candidate_input_file}"
        )
    if not settings.candidate_members_file.exists():
        raise FileNotFoundError(
            f"Candidate members file not found: {settings.candidate_members_file}"
        )

    (
        compounds_out,
        aliases_out,
        bridge_out,
        compound_review_rows_out,
        plant_review_rows_out,
        candidate_map_out,
        summary,
    ) = build_canonical_tables(settings, logger)

    compounds_file = settings.build_out_dir / "compounds.csv"
    aliases_file = settings.build_out_dir / "compound_aliases.csv"
    bridge_file = settings.build_out_dir / "plant_compounds.csv"
    review_file = settings.build_out_dir / "compound_review.csv"
    plant_review_file = settings.build_out_dir / "plant_compound_review.csv"
    candidate_map_file = settings.build_out_dir / "compound_candidate_map.csv"
    summary_file = settings.build_out_dir / "build_canonical_summary.json"

    _write_csv_local(compounds_file, compounds_out, COMPOUNDS_COLUMNS)
    _write_csv_local(aliases_file, aliases_out, ALIASES_COLUMNS)
    _write_csv_local(bridge_file, bridge_out, PLANT_COMPOUNDS_COLUMNS)
    _write_csv_local(review_file, compound_review_rows_out, REVIEW_COLUMNS)
    _write_csv_local(plant_review_file, plant_review_rows_out, PLANT_REVIEW_COLUMNS)
    _write_csv_local(candidate_map_file, candidate_map_out, CANDIDATE_MAP_COLUMNS)
    _write_json_local(summary_file, summary)

    logger.info("Candidate map rows: %d", len(candidate_map_out))
    logger.info("Candidate map file: %s", candidate_map_file)
    logger.info("Canonical compounds: %d", len(compounds_out))
    logger.info("Accepted compounds: %d", summary["accepted_compounds"])
    logger.info("Provisional compounds: %d", summary["provisional_compounds"])
    logger.info("Alias rows: %d", len(aliases_out))
    logger.info("Plant-compound rows: %d", len(bridge_out))
    logger.info("Compound review rows: %d", len(compound_review_rows_out))
    logger.info("Plant review rows: %d", len(plant_review_rows_out))
    logger.info("Compounds file: %s", compounds_file)
    logger.info("Aliases file: %s", aliases_file)
    logger.info("Plant-compounds file: %s", bridge_file)
    logger.info("Compound review file: %s", review_file)
    logger.info("Plant review file: %s", plant_review_file)
    logger.info("Summary file: %s", summary_file)
    logger.info("Log file: %s", log_path)
    logger.info("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
