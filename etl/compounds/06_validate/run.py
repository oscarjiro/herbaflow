"""Validate the final canonical compound outputs before export.

Purpose
-------
This script is the validation gate for the compound ETL pipeline. It validates the
outputs of `05_build_canonical`, keeps compound-level review separate from plant-
bridge review, checks schema and referential integrity, performs chemistry sanity
checks, and produces a validation report for downstream export gating.

Inputs
------
Default inputs come from `compounds/05_build_canonical/out/`.

Required inputs:
- `compounds.csv`
- `compound_aliases.csv`
- `compound_candidate_map.csv`
- `compound_review.csv`
- `plant_compounds.csv`
- `plant_compound_review.csv`
- `build_canonical_summary.json`
- settings from `compounds/settings.yml`

Optional inputs:
- plant ETL canonical plant output for plant ID sanity checks
- plant ETL alias outputs if available

Outputs
-------
Written only to `compounds/06_validate/out/`:
- `validation_report.json`
- `validation_issues.csv`
- `validation_counts.csv`
- validated pass-through copies of the 05 tables:
  - `validated_compounds.csv`
  - `validated_compound_aliases.csv`
  - `validated_compound_candidate_map.csv`
  - `validated_compound_review.csv`
  - `validated_plant_compounds.csv`
  - `validated_plant_compound_review.csv`
- log file in `out/logs/`

Behavior
--------
- Does not rewrite or canonicalize data.
- Does not enrich data.
- Does not merge plant-review back into compound-review.
- Fails on structural and referential errors that would break export.
- Warns on non-blocking chemistry anomalies and small review queues.
- Returns non-zero exit code on validation failure.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/

import argparse
import csv
import json
import logging
import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

from shared.identity import cas_checksum_valid, formula_matches, hill_formula, normalize_cas

try:
    import yaml
except ImportError as exc:  # pragma: no cover
    raise SystemExit("PyYAML is required to run this script.") from exc


COMPOUNDS_COLUMNS = [
    "compound_id",
    "canonical_key",
    "canonical_name",
    "inchi_key",
    "connectivity_key",
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
    "is_pains_positive",
    "source_name",
    "source_url",
    "retrieved_at",
    "canonical_status",
    "canonical_strategy",
    "canonical_reason",
    "match_strategy",
    "evidence_type",
    "enrichment_confidence",
    "evidence_count",
    "plant_count",
]

ALIASES_COLUMNS = [
    "compound_alias_id",
    "compound_id",
    "alias_name",
    "alias_key",
    "alias_type",
    "retrieved_at",
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

COMPOUND_REVIEW_COLUMNS = [
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

PLANT_COMPOUNDS_COLUMNS = [
    "plant_compound_id",
    "plant_id",
    "compound_id",
    "source_name",
    "source_url",
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

SUMMARY_REQUIRED_KEYS = [
    "candidate_rows",
    "candidate_member_rows",
    "accepted_candidate_count",
    "provisional_candidate_count",
    "review_candidate_count",
    "unresolved_candidate_count",
    "canonical_compound_count",
    "accepted_compounds",
    "provisional_compounds",
    "candidate_map_row_count",
    "alias_row_count",
    "plant_compound_row_count",
    "compound_review_row_count",
    "plant_review_row_count",
    "unmapped_plant_rows",
]

EXPECTED_COMPOUND_REVIEW_ISSUES = {
    "missing_canonical_key",
    "too_weak_or_contradictory",
    "review_salvageable_identity",
    "strong_identity_salvage",
    "matched_high_confidence_strong_identity",
    "insufficient_identity_support",
    "not_strong_enough",
    "review",
    "unresolved",
}

EXPECTED_PLANT_REVIEW_ISSUES = {
    "unmapped_plant_reference",
    "canonical_plant_id_missing",
}

GENERIC_ALIAS_KEYS = {
    "compound",
    "unknown",
    "unidentified",
    "extract",
    "metabolite",
}

INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")
FORMULA_RE = re.compile(r"^[A-Z][A-Za-z0-9().·+\-]*$")


@dataclass(frozen=True)
class Settings:
    module_root: Path
    project_root: Path
    validate_out_dir: Path
    validate_log_dir: Path
    build_out_dir: Path
    dedupe_out_dir: Path
    plant_export_csv: Optional[Path]
    overwrite_outputs: bool
    run_id_prefix: str
    timestamp_format: str
    batch_id: str


@dataclass
class Issue:
    table_name: str
    row_identifier: str
    issue_type: str
    issue_reason: str
    severity: str  # error | warning
    source_file: str
    details: Dict[str, Any]


def normalize_whitespace(value: Optional[str]) -> str:
    if value is None:
        return ""
    return " ".join(str(value).split())


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


def parse_int(value: Optional[str]) -> Optional[int]:
    text = normalize_whitespace(value)
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        try:
            f = float(text)
            if f.is_integer():
                return int(f)
        except ValueError:
            pass
    return None


def normalize_key(value: Optional[str]) -> str:
    text = normalize_whitespace(value).strip().lower()
    if not text:
        return ""
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def stable_run_id(settings: Settings) -> str:
    if settings.batch_id and settings.batch_id != "auto":
        return f"{settings.run_id_prefix}_{settings.batch_id}"
    return f"{settings.run_id_prefix}_{datetime.now(timezone.utc).strftime(settings.timestamp_format)}"


def configure_logging(log_dir: Path, run_id: str) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / f"validate_compounds_{run_id}.log"

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


def resolve_rel(base: Path, value: Optional[str], default: str) -> Path:
    raw = value or default
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base / p).resolve()


def load_settings(settings_path: Path) -> Settings:
    with settings_path.open("r", encoding="utf-8") as f:
        config = yaml.safe_load(f) or {}

    module_root = settings_path.parent.resolve()
    project_root = (module_root / config["project"]["project_root"]).resolve()

    def resolve_project_rel(value: str) -> Path:
        p = Path(value)
        if p.is_absolute():
            return p
        return (project_root / p).resolve()

    paths_cfg = config.get("paths", {})
    step_dirs_cfg = paths_cfg.get("step_dirs", {})
    plant_etl_cfg = paths_cfg.get("plant_etl", {})
    batch_cfg = config.get("batch", {})

    dedupe_out_dir = resolve_project_rel(
        step_dirs_cfg.get("dedupe_candidates_out", "compounds/03_dedupe_candidates/out")
    )
    build_out_dir = resolve_project_rel(
        step_dirs_cfg.get("build_canonical_out", "compounds/05_build_canonical/out")
    )
    validate_out_dir = resolve_project_rel(
        step_dirs_cfg.get("validate_out", "compounds/06_validate/out")
    )
    validate_log_dir = resolve_project_rel(
        paths_cfg.get("logs", {}).get("validate", "compounds/06_validate/out/logs")
    )

    plant_export_value = plant_etl_cfg.get("canonical_plants_csv")

    return Settings(
        module_root=module_root,
        project_root=project_root,
        validate_out_dir=validate_out_dir,
        validate_log_dir=validate_log_dir,
        build_out_dir=build_out_dir,
        dedupe_out_dir=dedupe_out_dir,
        plant_export_csv=(
            resolve_project_rel(plant_export_value) if plant_export_value else None
        ),
        overwrite_outputs=bool(batch_cfg.get("overwrite_outputs", False)),
        run_id_prefix=str(batch_cfg.get("run_id_prefix", "compounds")),
        timestamp_format=str(batch_cfg.get("timestamp_format", "%Y%m%d_%H%M%S")),
        batch_id=str(batch_cfg.get("batch_id", "auto")),
    )


def read_csv_rows(path: Path) -> Tuple[List[Dict[str, str]], List[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError(f"File has no header row: {path}")
        rows = list(reader)
        return rows, list(reader.fieldnames)


def write_csv(
    path: Path, rows: List[Dict[str, Any]], fieldnames: Sequence[str], overwrite: bool
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(fieldnames), extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: Dict[str, Any], overwrite: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.unlink(missing_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")


def load_table(
    path: Path, required_columns: Sequence[str], label: str
) -> Tuple[List[Dict[str, str]], List[str]]:
    if not path.exists():
        raise FileNotFoundError(f"Missing required input: {path}")
    rows, fieldnames = read_csv_rows(path)
    ensure_columns(fieldnames, required_columns, label)
    return rows, fieldnames


def ensure_columns(
    fieldnames: Sequence[str], required: Sequence[str], label: str
) -> None:
    missing = [c for c in required if c not in fieldnames]
    if missing:
        raise ValueError(f"{label} is missing expected columns: {missing}")


def add_issue(
    issues: List[Issue],
    table_name: str,
    row_identifier: str,
    issue_type: str,
    issue_reason: str,
    severity: str,
    source_file: str,
    **details: Any,
) -> None:
    issues.append(
        Issue(
            table_name=table_name,
            row_identifier=row_identifier,
            issue_type=issue_type,
            issue_reason=issue_reason,
            severity=severity,
            source_file=source_file,
            details=details,
        )
    )


def stable_sort_rows(
    rows: List[Dict[str, str]], key_fields: Sequence[str]
) -> List[Dict[str, str]]:
    if not rows:
        return rows
    if any(k in rows[0] for k in key_fields):
        return sorted(
            rows,
            key=lambda r: tuple(normalize_whitespace(r.get(k, "")) for k in key_fields),
        )
    return rows


def load_optional_plant_ids(
    settings: Settings, logger: logging.Logger
) -> Tuple[set[str], bool]:
    plant_ids: set[str] = set()
    loaded = False
    rows: List[Dict[str, str]] = []
    fields: List[str] = []

    try:
        rows, fields = read_csv_rows(settings.plant_export_csv)
    except Exception as exc:  # pragma: no cover - optional input only
        logger.warning(
            "Could not load optional plant file %s: %s", settings.plant_export_csv, exc
        )
    canonical_col = next(
        (c for c in ("plant_id", "canonical_plant_id") if c in fields), None
    )

    if not canonical_col:
        return plant_ids, loaded

    loaded = True
    for row in rows:
        pid = normalize_whitespace(row.get(canonical_col, ""))
        if pid:
            plant_ids.add(pid)

    return plant_ids, loaded


def validate_compounds(
    rows: List[Dict[str, str]],
    source_file: str,
    issues: List[Issue],
    warnings_summary: Dict[str, int],
) -> Dict[str, Any]:
    compound_ids: set[str] = set()
    canonical_keys: set[str] = set()
    compound_id_counts: Counter[str] = Counter()
    canonical_key_counts: Counter[str] = Counter()
    inchi_index: Dict[str, List[str]] = defaultdict(list)
    pubchem_index: Dict[str, List[str]] = defaultdict(list)
    chembl_index: Dict[str, List[str]] = defaultdict(list)

    for i, row in enumerate(rows, start=1):
        rid = normalize_whitespace(row.get("compound_id", "")) or f"row_{i}"
        compound_id = normalize_whitespace(row.get("compound_id", ""))
        canonical_key = normalize_whitespace(row.get("canonical_key", ""))
        name = normalize_whitespace(row.get("canonical_name", ""))
        status = normalize_whitespace(row.get("canonical_status", ""))
        evidence_count = parse_int(row.get("evidence_count", ""))
        plant_count = parse_int(row.get("plant_count", ""))
        inchi = normalize_whitespace(row.get("inchi_key", ""))
        cas_id = normalize_whitespace(row.get("cas_id", ""))
        mw = normalize_whitespace(row.get("molecular_weight", ""))
        formula = normalize_whitespace(row.get("molecular_formula", ""))
        pubchem = normalize_whitespace(row.get("pubchem_cid", ""))
        chembl = normalize_whitespace(row.get("chembl_id", ""))

        compound_id_counts[compound_id] += 1
        canonical_key_counts[canonical_key] += 1

        if not compound_id:
            add_issue(
                issues,
                "compounds.csv",
                rid,
                "missing_compound_id",
                "compound_id is blank",
                "error",
                source_file,
            )
        if not canonical_key:
            add_issue(
                issues,
                "compounds.csv",
                rid,
                "missing_canonical_key",
                "canonical_key is blank",
                "error",
                source_file,
            )
        if not name:
            add_issue(
                issues,
                "compounds.csv",
                rid,
                "blank_canonical_name",
                "canonical_name is blank",
                "error",
                source_file,
            )

        if status not in {"accepted", "provisional"}:
            add_issue(
                issues,
                "compounds.csv",
                rid,
                "invalid_canonical_status",
                f"canonical_status={status!r}",
                "error",
                source_file,
            )

        if evidence_count is None or evidence_count <= 0:
            add_issue(
                issues,
                "compounds.csv",
                rid,
                "invalid_evidence_count",
                f"evidence_count={row.get('evidence_count', '')!r}",
                "error",
                source_file,
            )
        if plant_count is None or plant_count < 0:
            add_issue(
                issues,
                "compounds.csv",
                rid,
                "invalid_plant_count",
                f"plant_count={row.get('plant_count', '')!r}",
                "error",
                source_file,
            )

        if inchi:
            if not INCHIKEY_RE.fullmatch(inchi):
                add_issue(
                    issues,
                    "compounds.csv",
                    rid,
                    "invalid_inchikey_format",
                    f"inchi_key={inchi!r}",
                    "warning",
                    source_file,
                )
            inchi_index[inchi].append(compound_id)
        if cas_id:
            cas_norm = normalize_cas(cas_id)[0]
            if not cas_checksum_valid(cas_norm):
                add_issue(
                    issues,
                    "compounds.csv",
                    rid,
                    "invalid_cas_format",
                    f"cas_id={cas_id!r}",
                    "warning",
                    source_file,
                )
        if mw:
            if parse_float(mw) is None:
                add_issue(
                    issues,
                    "compounds.csv",
                    rid,
                    "invalid_molecular_weight",
                    f"molecular_weight={mw!r}",
                    "warning",
                    source_file,
                )
            elif (parse_float(mw) or 0.0) <= 0:
                add_issue(
                    issues,
                    "compounds.csv",
                    rid,
                    "nonpositive_molecular_weight",
                    f"molecular_weight={mw!r}",
                    "warning",
                    source_file,
                )
        if formula and not FORMULA_RE.fullmatch(formula):
            add_issue(
                issues,
                "compounds.csv",
                rid,
                "unusual_formula_string",
                f"molecular_formula={formula!r}",
                "warning",
                source_file,
            )

        if pubchem:
            pubchem_index[pubchem].append(compound_id)
        if chembl:
            chembl_index[chembl].append(compound_id)

    for cid, count in compound_id_counts.items():
        if cid and count > 1:
            add_issue(
                issues,
                "compounds.csv",
                cid,
                "duplicate_compound_id",
                f"compound_id appears {count} times",
                "error",
                source_file,
            )

    for key, count in canonical_key_counts.items():
        if key and count > 1:
            add_issue(
                issues,
                "compounds.csv",
                key,
                "duplicate_canonical_key",
                f"canonical_key appears {count} times",
                "error",
                source_file,
            )

    for inchi, ids in inchi_index.items():
        unique_ids = sorted(set(ids))
        if len(unique_ids) > 1:
            add_issue(
                issues,
                "compounds.csv",
                inchi,
                "duplicate_inchikey_across_compounds",
                "same InChIKey used by multiple canonical compounds",
                "warning",
                source_file,
                compound_ids=unique_ids,
            )

    for pubchem, ids in pubchem_index.items():
        unique_ids = sorted(set(ids))
        if len(unique_ids) > 1:
            add_issue(
                issues,
                "compounds.csv",
                pubchem,
                "duplicate_pubchem_cid_across_compounds",
                "same PubChem CID used by multiple canonical compounds",
                "warning",
                source_file,
                compound_ids=unique_ids,
            )

    for chembl, ids in chembl_index.items():
        unique_ids = sorted(set(ids))
        if len(unique_ids) > 1:
            add_issue(
                issues,
                "compounds.csv",
                chembl,
                "duplicate_chembl_id_across_compounds",
                "same ChEMBL ID used by multiple canonical compounds",
                "warning",
                source_file,
                compound_ids=unique_ids,
            )

    return {
        "row_count": len(rows),
        "unique_compound_ids": len(
            {
                normalize_whitespace(r.get("compound_id", ""))
                for r in rows
                if normalize_whitespace(r.get("compound_id", ""))
            }
        ),
        "unique_canonical_keys": len(
            {
                normalize_whitespace(r.get("canonical_key", ""))
                for r in rows
                if normalize_whitespace(r.get("canonical_key", ""))
            }
        ),
    }


def load_raw_formula_by_candidate(
    dedupe_out_dir: Path, logger: logging.Logger
) -> Dict[str, str]:
    """Map compound_candidate_id -> raw KNApSAcK representative formula (03 output)."""
    path = dedupe_out_dir / "compound_candidates.csv"
    if not path.exists():
        logger.warning(
            "compound_candidates.csv not found; skipping formula-consistency check: %s",
            path,
        )
        return {}
    rows, fields = read_csv_rows(path)
    if "compound_candidate_id" not in fields or "representative_formula" not in fields:
        return {}
    out: Dict[str, str] = {}
    for r in rows:
        cid = normalize_whitespace(r.get("compound_candidate_id", ""))
        rf = normalize_whitespace(r.get("representative_formula", ""))
        if cid and rf:
            out[cid] = rf
    return out


def validate_formula_consistency(
    compound_rows: List[Dict[str, str]],
    candidate_map_rows: List[Dict[str, str]],
    raw_formula_by_candidate: Dict[str, str],
    source_file: str,
    issues: List[Issue],
) -> Dict[str, Any]:
    """Correctness check: a resolved structure must preserve the raw source formula.

    For every canonical compound that carries a resolved structure (an InChIKey), the
    resolved ``molecular_formula`` must equal the raw KNApSAcK formula of its
    contributing candidate(s), compared Hill-normalized via
    ``shared.identity.formula_matches``. The corroboration gate in enrichment (04)
    should make this hold for every accepted compound, so this is a regression guard.
    Mismatches are reported as warnings (never a hard pipeline failure).
    """
    raw_by_compound: Dict[str, set[str]] = defaultdict(set)
    for r in candidate_map_rows:
        cid = normalize_whitespace(r.get("compound_id", ""))
        cand = normalize_whitespace(r.get("compound_candidate_id", ""))
        if not cid or not cand:
            continue
        rf = raw_formula_by_candidate.get(cand, "")
        if rf:
            raw_by_compound[cid].add(rf)

    checked = 0
    mismatches = 0
    for row in compound_rows:
        if not normalize_whitespace(row.get("inchi_key", "")):
            continue  # only compounds with a resolved structure
        resolved = normalize_whitespace(row.get("molecular_formula", ""))
        if not hill_formula(resolved):
            continue  # resolved formula not comparable (blank / salt / unparseable)
        cid = normalize_whitespace(row.get("compound_id", ""))
        raws = [f for f in raw_by_compound.get(cid, set()) if hill_formula(f)]
        if not raws:
            continue
        checked += 1
        if not any(formula_matches(resolved, rf) for rf in raws):
            mismatches += 1
            add_issue(
                issues,
                "compounds.csv",
                cid or "row",
                "formula_mismatch_resolved_vs_raw",
                f"resolved molecular_formula={resolved!r} does not match raw source formula(s)={sorted(raws)!r}",
                "warning",
                source_file,
                resolved_formula=resolved,
                raw_formulas=sorted(raws),
            )
    return {"formula_checked": checked, "formula_mismatches": mismatches}


def validate_aliases(
    rows: List[Dict[str, str]],
    source_file: str,
    issues: List[Issue],
    compound_ids: set[str],
) -> Dict[str, Any]:
    alias_ids: Counter[str] = Counter()
    compound_alias_keys: set[Tuple[str, str]] = set()
    alias_count_by_compound: Counter[str] = Counter()

    for i, row in enumerate(rows, start=1):
        rid = normalize_whitespace(row.get("compound_alias_id", "")) or f"row_{i}"
        alias_id = normalize_whitespace(row.get("compound_alias_id", ""))
        compound_id = normalize_whitespace(row.get("compound_id", ""))
        alias_name = normalize_whitespace(row.get("alias_name", ""))
        alias_key = normalize_whitespace(row.get("alias_key", ""))
        alias_type = normalize_whitespace(row.get("alias_type", ""))

        alias_ids[alias_id] += 1
        if compound_id:
            alias_count_by_compound[compound_id] += 1

        if not alias_id:
            add_issue(
                issues,
                "compound_aliases.csv",
                rid,
                "missing_alias_id",
                "compound_alias_id is blank",
                "error",
                source_file,
            )
        if not compound_id:
            add_issue(
                issues,
                "compound_aliases.csv",
                rid,
                "missing_compound_id",
                "compound_id is blank",
                "error",
                source_file,
            )
        elif compound_id not in compound_ids:
            add_issue(
                issues,
                "compound_aliases.csv",
                rid,
                "orphan_alias_compound",
                f"compound_id={compound_id!r} not found in compounds.csv",
                "error",
                source_file,
            )

        if not alias_name or len(alias_name) < 2:
            add_issue(
                issues,
                "compound_aliases.csv",
                rid,
                "blank_or_short_alias",
                "alias_name is empty or too short",
                "warning",
                source_file,
            )
        if not alias_key:
            add_issue(
                issues,
                "compound_aliases.csv",
                rid,
                "missing_alias_key",
                "alias_key is blank",
                "error",
                source_file,
            )

        if alias_key in GENERIC_ALIAS_KEYS and alias_type not in {
            "cas_id",
            "source_compound_id",
        }:
            add_issue(
                issues,
                "compound_aliases.csv",
                rid,
                "generic_alias_noise",
                f"alias_key={alias_key!r}",
                "warning",
                source_file,
            )

        pair = (compound_id, alias_key)
        if compound_id and alias_key:
            if pair in compound_alias_keys:
                add_issue(
                    issues,
                    "compound_aliases.csv",
                    rid,
                    "duplicate_compound_alias_pair",
                    f"(compound_id, alias_key)={pair!r}",
                    "error",
                    source_file,
                )
            compound_alias_keys.add(pair)

        if alias_id:
            if alias_ids[alias_id] > 1:
                add_issue(
                    issues,
                    "compound_aliases.csv",
                    rid,
                    "duplicate_alias_id",
                    f"compound_alias_id={alias_id!r}",
                    "error",
                    source_file,
                )

    for compound_id, count in alias_count_by_compound.items():
        if count > 32:
            add_issue(
                issues,
                "compound_aliases.csv",
                compound_id,
                "alias_inflation",
                f"{count} aliases for compound",
                "warning",
                source_file,
            )

    return {
        "row_count": len(rows),
        "unique_alias_ids": len(alias_ids),
        "unique_compound_alias_pairs": len(compound_alias_keys),
    }


def validate_candidate_map(
    rows: List[Dict[str, str]],
    source_file: str,
    issues: List[Issue],
    compound_ids: set[str],
    compound_key_by_id: Dict[str, str],
    expected_candidate_rows: Optional[int],
) -> Dict[str, Any]:
    map_ids: Counter[str] = Counter()
    candidate_ids: Counter[str] = Counter()
    statuses = {"accepted", "provisional", "review", "unresolved"}
    with_compound = 0
    without_compound = 0

    for i, row in enumerate(rows, start=1):
        rid = (
            normalize_whitespace(row.get("compound_candidate_map_id", "")) or f"row_{i}"
        )
        map_id = normalize_whitespace(row.get("compound_candidate_map_id", ""))
        candidate_id = normalize_whitespace(row.get("compound_candidate_id", ""))
        compound_id = normalize_whitespace(row.get("compound_id", ""))
        canonical_key = normalize_whitespace(row.get("canonical_key", ""))
        canonical_status = normalize_whitespace(row.get("canonical_status", ""))
        candidate_status = normalize_whitespace(row.get("candidate_status", ""))
        enrichment_status = normalize_whitespace(row.get("enrichment_status", ""))
        decision_reason = normalize_whitespace(row.get("decision_reason", ""))
        conf = parse_float(row.get("confidence", ""))

        map_ids[map_id] += 1
        candidate_ids[candidate_id] += 1
        if compound_id:
            with_compound += 1
        else:
            without_compound += 1

        if not map_id:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "missing_map_id",
                "compound_candidate_map_id is blank",
                "error",
                source_file,
            )
        if not candidate_id:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "missing_candidate_id",
                "compound_candidate_id is blank",
                "error",
                source_file,
            )
        if canonical_status not in statuses:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "invalid_canonical_status",
                f"canonical_status={canonical_status!r}",
                "error",
                source_file,
            )
        if conf is None or not (0.0 <= conf <= 1.0):
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "invalid_confidence",
                f"confidence={row.get('confidence', '')!r}",
                "error",
                source_file,
            )

        if compound_id and compound_id not in compound_ids:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "orphan_candidate_map_compound",
                f"compound_id={compound_id!r} not found in compounds.csv",
                "error",
                source_file,
            )
        if compound_id and canonical_key and compound_id in compound_key_by_id:
            if compound_key_by_id[compound_id] != canonical_key:
                add_issue(
                    issues,
                    "compound_candidate_map.csv",
                    rid,
                    "canonical_key_mismatch",
                    f"map canonical_key={canonical_key!r} does not match compounds.csv",
                    "error",
                    source_file,
                    compound_id=compound_id,
                    compounds_canonical_key=compound_key_by_id[compound_id],
                )

        if canonical_status in {"accepted", "provisional"} and not compound_id:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "missing_compound_for_canonical_candidate",
                f"status={canonical_status!r} but compound_id blank",
                "error",
                source_file,
            )

        if canonical_status in {"review", "unresolved"} and compound_id:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "unexpected_compound_for_review_candidate",
                f"status={canonical_status!r} but compound_id populated",
                "warning",
                source_file,
            )

        if canonical_status in {"accepted", "provisional"} and not canonical_key:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "missing_canonical_key_for_mapped_candidate",
                "canonical_key blank for accepted/provisional candidate",
                "error",
                source_file,
            )

        if not decision_reason:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "missing_decision_reason",
                "decision_reason is blank",
                "warning",
                source_file,
            )
        if not candidate_status:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "missing_candidate_status",
                "candidate_status is blank",
                "warning",
                source_file,
            )
        if not enrichment_status:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                rid,
                "missing_enrichment_status",
                "enrichment_status is blank",
                "warning",
                source_file,
            )

    for mid, count in map_ids.items():
        if mid and count > 1:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                mid,
                "duplicate_candidate_map_id",
                f"compound_candidate_map_id appears {count} times",
                "error",
                source_file,
            )

    for cid, count in candidate_ids.items():
        if cid and count > 1:
            add_issue(
                issues,
                "compound_candidate_map.csv",
                cid,
                "duplicate_candidate_id_in_map",
                f"compound_candidate_id appears {count} times",
                "error",
                source_file,
            )

    if (
        expected_candidate_rows is not None
        and len(candidate_ids) != expected_candidate_rows
    ):
        add_issue(
            issues,
            "compound_candidate_map.csv",
            "table",
            "candidate_row_count_mismatch",
            f"candidate map unique candidates={len(candidate_ids)} expected={expected_candidate_rows}",
            "error",
            source_file,
        )

    return {
        "row_count": len(rows),
        "unique_candidate_ids": len(candidate_ids),
        "with_compound_id": with_compound,
        "without_compound_id": without_compound,
    }


def validate_compound_review(
    rows: List[Dict[str, str]],
    source_file: str,
    issues: List[Issue],
    compound_ids: set[str],
) -> Dict[str, Any]:
    ids: Counter[str] = Counter()
    issue_types = Counter()

    for i, row in enumerate(rows, start=1):
        rid = normalize_whitespace(row.get("compound_review_id", "")) or f"row_{i}"
        review_id = normalize_whitespace(row.get("compound_review_id", ""))
        compound_id = normalize_whitespace(row.get("compound_id", ""))
        issue_type = normalize_whitespace(row.get("issue_type", ""))
        issue_reason = normalize_whitespace(row.get("issue_reason", ""))
        canonical_status = normalize_whitespace(row.get("canonical_status", ""))
        evidence_json = normalize_whitespace(row.get("evidence_summary_json", ""))

        ids[review_id] += 1
        issue_types[issue_type] += 1

        if not review_id:
            add_issue(
                issues,
                "compound_review.csv",
                rid,
                "missing_review_id",
                "compound_review_id is blank",
                "error",
                source_file,
            )
        if issue_type in EXPECTED_PLANT_REVIEW_ISSUES:
            add_issue(
                issues,
                "compound_review.csv",
                rid,
                "bridge_row_in_compound_review",
                f"issue_type={issue_type!r} belongs in plant review",
                "error",
                source_file,
            )
        if issue_type and issue_type not in EXPECTED_COMPOUND_REVIEW_ISSUES:
            add_issue(
                issues,
                "compound_review.csv",
                rid,
                "unexpected_compound_review_issue",
                f"issue_type={issue_type!r}",
                "warning",
                source_file,
            )
        if canonical_status and canonical_status not in {"review", "unresolved"}:
            add_issue(
                issues,
                "compound_review.csv",
                rid,
                "unexpected_review_status",
                f"canonical_status={canonical_status!r}",
                "warning",
                source_file,
            )
        if compound_id and compound_id not in compound_ids:
            add_issue(
                issues,
                "compound_review.csv",
                rid,
                "orphan_compound_review_compound",
                f"compound_id={compound_id!r} not found in compounds.csv",
                "error",
                source_file,
            )

        if evidence_json:
            try:
                json.loads(evidence_json)
            except json.JSONDecodeError:
                add_issue(
                    issues,
                    "compound_review.csv",
                    rid,
                    "invalid_evidence_json",
                    "evidence_summary_json is not valid JSON",
                    "error",
                    source_file,
                )
        else:
            add_issue(
                issues,
                "compound_review.csv",
                rid,
                "missing_evidence_json",
                "evidence_summary_json is blank",
                "warning",
                source_file,
            )

    for rid, count in ids.items():
        if rid and count > 1:
            add_issue(
                issues,
                "compound_review.csv",
                rid,
                "duplicate_review_id",
                f"compound_review_id appears {count} times",
                "error",
                source_file,
            )

    return {
        "row_count": len(rows),
        "unique_review_ids": len(ids),
        "issue_type_counts": dict(issue_types),
    }


def validate_plant_compounds(
    rows: List[Dict[str, str]],
    source_file: str,
    issues: List[Issue],
    compound_ids: set[str],
    canonical_plant_ids: set[str],
    plant_schema_loaded: bool,
) -> Dict[str, Any]:
    ids: Counter[str] = Counter()
    pair_keys: set[Tuple[str, str]] = set()

    for i, row in enumerate(rows, start=1):
        rid = normalize_whitespace(row.get("plant_compound_id", "")) or f"row_{i}"
        bridge_id = normalize_whitespace(row.get("plant_compound_id", ""))
        plant_id = normalize_whitespace(row.get("plant_id", ""))
        compound_id = normalize_whitespace(row.get("compound_id", ""))

        ids[bridge_id] += 1

        if not bridge_id:
            add_issue(
                issues,
                "plant_compounds.csv",
                rid,
                "missing_bridge_id",
                "plant_compound_id is blank",
                "error",
                source_file,
            )
        if not plant_id:
            add_issue(
                issues,
                "plant_compounds.csv",
                rid,
                "missing_plant_id",
                "plant_id is blank",
                "error",
                source_file,
            )
        if not compound_id:
            add_issue(
                issues,
                "plant_compounds.csv",
                rid,
                "missing_compound_id",
                "compound_id is blank",
                "error",
                source_file,
            )
        elif compound_id not in compound_ids:
            add_issue(
                issues,
                "plant_compounds.csv",
                rid,
                "orphan_bridge_compound",
                f"compound_id={compound_id!r} not found in compounds.csv",
                "error",
                source_file,
            )

        if (
            plant_schema_loaded
            and canonical_plant_ids
            and plant_id
            and plant_id not in canonical_plant_ids
        ):
            add_issue(
                issues,
                "plant_compounds.csv",
                rid,
                "unknown_canonical_plant_id",
                f"plant_id={plant_id!r} not found in plant export",
                "warning",
                source_file,
            )

        pair = (plant_id, compound_id)
        if plant_id and compound_id:
            if pair in pair_keys:
                add_issue(
                    issues,
                    "plant_compounds.csv",
                    rid,
                    "duplicate_bridge_pair",
                    f"(plant_id, compound_id)={pair!r}",
                    "error",
                    source_file,
                )
            pair_keys.add(pair)

    for bid, count in ids.items():
        if bid and count > 1:
            add_issue(
                issues,
                "plant_compounds.csv",
                bid,
                "duplicate_bridge_id",
                f"plant_compound_id appears {count} times",
                "error",
                source_file,
            )

    return {
        "row_count": len(rows),
        "unique_bridge_ids": len(ids),
        "unique_pairs": len(pair_keys),
    }


def validate_plant_review(
    rows: List[Dict[str, str]],
    source_file: str,
    issues: List[Issue],
    compound_ids: set[str],
    canonical_plant_ids: set[str],
    plant_schema_loaded: bool,
) -> Dict[str, Any]:
    ids: Counter[str] = Counter()
    issue_types = Counter()

    for i, row in enumerate(rows, start=1):
        rid = (
            normalize_whitespace(row.get("plant_compound_review_id", "")) or f"row_{i}"
        )
        review_id = normalize_whitespace(row.get("plant_compound_review_id", ""))
        compound_id = normalize_whitespace(row.get("compound_id", ""))
        issue_type = normalize_whitespace(row.get("issue_type", ""))
        canonical_plant_id = normalize_whitespace(row.get("canonical_plant_id", ""))
        evidence_json = normalize_whitespace(row.get("evidence_summary_json", ""))

        ids[review_id] += 1
        issue_types[issue_type] += 1

        if not review_id:
            add_issue(
                issues,
                "plant_compound_review.csv",
                rid,
                "missing_review_id",
                "plant_compound_review_id is blank",
                "error",
                source_file,
            )
        if issue_type not in EXPECTED_PLANT_REVIEW_ISSUES:
            add_issue(
                issues,
                "plant_compound_review.csv",
                rid,
                "unexpected_plant_review_issue",
                f"issue_type={issue_type!r}",
                "warning",
                source_file,
            )
        if canonical_plant_id:
            add_issue(
                issues,
                "plant_compound_review.csv",
                rid,
                "canonical_plant_id_should_be_blank",
                "canonical_plant_id should be blank in plant review",
                "error",
                source_file,
            )
        if compound_id and compound_id not in compound_ids:
            add_issue(
                issues,
                "plant_compound_review.csv",
                rid,
                "orphan_plant_review_compound",
                f"compound_id={compound_id!r} not found in compounds.csv",
                "error",
                source_file,
            )
        if (
            plant_schema_loaded
            and canonical_plant_ids
            and canonical_plant_id
            and canonical_plant_id not in canonical_plant_ids
        ):
            add_issue(
                issues,
                "plant_compound_review.csv",
                rid,
                "unknown_canonical_plant_id",
                f"canonical_plant_id={canonical_plant_id!r} not found in plant export",
                "warning",
                source_file,
            )

        if evidence_json:
            try:
                json.loads(evidence_json)
            except json.JSONDecodeError:
                add_issue(
                    issues,
                    "plant_compound_review.csv",
                    rid,
                    "invalid_evidence_json",
                    "evidence_summary_json is not valid JSON",
                    "error",
                    source_file,
                )
        else:
            add_issue(
                issues,
                "plant_compound_review.csv",
                rid,
                "missing_evidence_json",
                "evidence_summary_json is blank",
                "warning",
                source_file,
            )

    for rid, count in ids.items():
        if rid and count > 1:
            add_issue(
                issues,
                "plant_compound_review.csv",
                rid,
                "duplicate_review_id",
                f"plant_compound_review_id appears {count} times",
                "error",
                source_file,
            )

    return {
        "row_count": len(rows),
        "unique_review_ids": len(ids),
        "issue_type_counts": dict(issue_types),
    }


def build_validation_counts(
    table_name: str,
    rows: List[Dict[str, str]],
    id_column: str,
    extra_unique_columns: Sequence[str],
    issues: List[Issue],
) -> Dict[str, Any]:
    unique_id_count = len(
        {
            normalize_whitespace(r.get(id_column, ""))
            for r in rows
            if normalize_whitespace(r.get(id_column, ""))
        }
    )
    extras = {}
    for col in extra_unique_columns:
        extras[f"unique_{col}_count"] = len(
            {
                normalize_whitespace(r.get(col, ""))
                for r in rows
                if normalize_whitespace(r.get(col, ""))
            }
        )
    issue_count = sum(1 for issue in issues if issue.table_name == table_name)
    return {
        "table_name": table_name,
        "row_count": len(rows),
        "unique_id_count": unique_id_count,
        "issue_count": issue_count,
        **extras,
    }


def compare_summary(
    summary: Dict[str, Any],
    actual: Dict[str, int],
    issues: List[Issue],
    source_file: str,
) -> None:
    mapping = {
        "candidate_rows": "candidate_map_row_count",
        "candidate_member_rows": "candidate_member_rows",
        "accepted_compounds": "accepted_compounds",
        "provisional_compounds": "provisional_compounds",
        "canonical_compound_count": "canonical_compound_count",
        "alias_row_count": "alias_row_count",
        "plant_compound_row_count": "plant_compound_row_count",
        "compound_review_row_count": "compound_review_row_count",
        "plant_review_row_count": "plant_review_row_count",
        "unmapped_plant_rows": "unmapped_plant_rows",
    }

    for key, actual_key in mapping.items():
        if key not in summary:
            add_issue(
                issues,
                "build_canonical_summary.json",
                "summary",
                "missing_summary_key",
                f"{key} not present in summary",
                "warning",
                source_file,
            )
            continue
        if key == "candidate_rows":
            expected = summary[key]
            if actual["candidate_map_unique_candidate_ids"] != expected:
                add_issue(
                    issues,
                    "build_canonical_summary.json",
                    "summary",
                    "candidate_row_count_mismatch",
                    f"summary candidate_rows={expected} actual unique candidate map ids={actual['candidate_map_unique_candidate_ids']}",
                    "error",
                    source_file,
                )
        elif key == "canonical_compound_count":
            expected = summary[key]
            if actual["compounds_row_count"] != expected:
                add_issue(
                    issues,
                    "build_canonical_summary.json",
                    "summary",
                    "compound_row_count_mismatch",
                    f"summary canonical_compound_count={expected} actual={actual['compounds_row_count']}",
                    "error",
                    source_file,
                )
        else:
            if actual_key in actual and summary[key] != actual[actual_key]:
                add_issue(
                    issues,
                    "build_canonical_summary.json",
                    "summary",
                    "summary_count_mismatch",
                    f"{key} summary={summary[key]} actual={actual[actual_key]}",
                    "error",
                    source_file,
                )


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate canonical compound outputs.")
    parser.add_argument(
        "--settings",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to the compound ETL settings.yml file.",
    )
    args = parser.parse_args()

    settings_path = Path(args.settings).resolve()
    settings = load_settings(settings_path)
    run_id = stable_run_id(settings)
    log_path = configure_logging(settings.validate_log_dir, run_id)
    logger = logging.getLogger("compounds.validate")

    logger.info("Starting validation run_id=%s", run_id)
    logger.info("Settings path: %s", settings_path)

    inputs = {
        "compounds.csv": settings.build_out_dir / "compounds.csv",
        "compound_aliases.csv": settings.build_out_dir / "compound_aliases.csv",
        "compound_candidate_map.csv": settings.build_out_dir
        / "compound_candidate_map.csv",
        "compound_review.csv": settings.build_out_dir / "compound_review.csv",
        "plant_compounds.csv": settings.build_out_dir / "plant_compounds.csv",
        "plant_compound_review.csv": settings.build_out_dir
        / "plant_compound_review.csv",
        "build_canonical_summary.json": settings.build_out_dir
        / "build_canonical_summary.json",
    }

    for label, path in inputs.items():
        if not path.exists():
            raise FileNotFoundError(f"Required input missing: {label} -> {path}")

    summary = {}
    with inputs["build_canonical_summary.json"].open("r", encoding="utf-8") as f:
        summary = json.load(f)

    compound_rows, _ = load_table(
        inputs["compounds.csv"], COMPOUNDS_COLUMNS, "compounds.csv"
    )
    alias_rows, _ = load_table(
        inputs["compound_aliases.csv"], ALIASES_COLUMNS, "compound_aliases.csv"
    )
    candidate_map_rows, _ = load_table(
        inputs["compound_candidate_map.csv"],
        CANDIDATE_MAP_COLUMNS,
        "compound_candidate_map.csv",
    )
    compound_review_rows, _ = load_table(
        inputs["compound_review.csv"], COMPOUND_REVIEW_COLUMNS, "compound_review.csv"
    )
    plant_rows, _ = load_table(
        inputs["plant_compounds.csv"], PLANT_COMPOUNDS_COLUMNS, "plant_compounds.csv"
    )
    plant_review_rows, _ = load_table(
        inputs["plant_compound_review.csv"],
        PLANT_REVIEW_COLUMNS,
        "plant_compound_review.csv",
    )

    plant_ids, plant_schema_loaded = load_optional_plant_ids(settings, logger)
    issues: List[Issue] = []

    # Validate summary keys first
    missing_summary_keys = [k for k in SUMMARY_REQUIRED_KEYS if k not in summary]
    for key in missing_summary_keys:
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "missing_summary_key",
            f"{key} missing from build_canonical_summary.json",
            "warning",
            str(inputs["build_canonical_summary.json"]),
        )

    compound_stats = validate_compounds(
        compound_rows, str(inputs["compounds.csv"]), issues, {}
    )
    compound_ids = {
        normalize_whitespace(r.get("compound_id", ""))
        for r in compound_rows
        if normalize_whitespace(r.get("compound_id", ""))
    }
    compound_key_by_id = {
        normalize_whitespace(r.get("compound_id", "")): normalize_whitespace(
            r.get("canonical_key", "")
        )
        for r in compound_rows
        if normalize_whitespace(r.get("compound_id", ""))
    }
    compound_stats["row_count"] = len(compound_rows)

    alias_stats = validate_aliases(
        alias_rows, str(inputs["compound_aliases.csv"]), issues, compound_ids
    )
    candidate_map_stats = validate_candidate_map(
        candidate_map_rows,
        str(inputs["compound_candidate_map.csv"]),
        issues,
        compound_ids,
        compound_key_by_id,
        expected_candidate_rows=summary.get("candidate_rows"),
    )
    raw_formula_by_candidate = load_raw_formula_by_candidate(
        settings.dedupe_out_dir, logger
    )
    formula_stats = validate_formula_consistency(
        compound_rows,
        candidate_map_rows,
        raw_formula_by_candidate,
        str(inputs["compounds.csv"]),
        issues,
    )
    logger.info(
        "Formula consistency: checked=%d mismatches=%d",
        formula_stats["formula_checked"],
        formula_stats["formula_mismatches"],
    )
    compound_review_stats = validate_compound_review(
        compound_review_rows, str(inputs["compound_review.csv"]), issues, compound_ids
    )
    plant_review_stats = validate_plant_review(
        plant_review_rows,
        str(inputs["plant_compound_review.csv"]),
        issues,
        compound_ids,
        plant_ids,
        plant_schema_loaded,
    )
    plant_stats = validate_plant_compounds(
        plant_rows,
        str(inputs["plant_compounds.csv"]),
        issues,
        compound_ids,
        plant_ids,
        plant_schema_loaded,
    )

    # Cross-table checks
    compound_map_ids = {
        normalize_whitespace(r.get("compound_candidate_id", ""))
        for r in candidate_map_rows
        if normalize_whitespace(r.get("compound_candidate_id", ""))
    }
    if len(compound_map_ids) != len(candidate_map_rows):
        add_issue(
            issues,
            "compound_candidate_map.csv",
            "table",
            "duplicate_candidate_ids_present",
            "candidate map has duplicate candidate IDs",
            "error",
            str(inputs["compound_candidate_map.csv"]),
        )

    if (
        summary.get("candidate_rows") is not None
        and len(candidate_map_rows) != summary["candidate_rows"]
    ):
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "candidate_map_row_count_mismatch",
            f"candidate_map rows={len(candidate_map_rows)} summary candidate_rows={summary['candidate_rows']}",
            "error",
            str(inputs["build_canonical_summary.json"]),
        )

    if (
        summary.get("compound_review_row_count") is not None
        and len(compound_review_rows) != summary["compound_review_row_count"]
    ):
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "compound_review_row_count_mismatch",
            f"compound_review rows={len(compound_review_rows)} summary={summary['compound_review_row_count']}",
            "error",
            str(inputs["build_canonical_summary.json"]),
        )

    if (
        summary.get("plant_review_row_count") is not None
        and len(plant_review_rows) != summary["plant_review_row_count"]
    ):
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "plant_review_row_count_mismatch",
            f"plant_review rows={len(plant_review_rows)} summary={summary['plant_review_row_count']}",
            "error",
            str(inputs["build_canonical_summary.json"]),
        )

    if (
        summary.get("alias_row_count") is not None
        and len(alias_rows) != summary["alias_row_count"]
    ):
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "alias_row_count_mismatch",
            f"alias rows={len(alias_rows)} summary={summary['alias_row_count']}",
            "error",
            str(inputs["build_canonical_summary.json"]),
        )

    if (
        summary.get("plant_compound_row_count") is not None
        and len(plant_rows) != summary["plant_compound_row_count"]
    ):
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "plant_bridge_row_count_mismatch",
            f"plant bridge rows={len(plant_rows)} summary={summary['plant_compound_row_count']}",
            "error",
            str(inputs["build_canonical_summary.json"]),
        )

    if (
        summary.get("canonical_compound_count") is not None
        and len(compound_rows) != summary["canonical_compound_count"]
    ):
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "compound_row_count_mismatch",
            f"compound rows={len(compound_rows)} summary={summary['canonical_compound_count']}",
            "error",
            str(inputs["build_canonical_summary.json"]),
        )

    # Validate review separation
    for row in compound_review_rows:
        if (
            normalize_whitespace(row.get("issue_type", ""))
            in EXPECTED_PLANT_REVIEW_ISSUES
        ):
            add_issue(
                issues,
                "compound_review.csv",
                normalize_whitespace(row.get("compound_review_id", "")) or "row",
                "bridge_row_in_compound_review",
                "bridge-level issue appeared in compound review",
                "error",
                str(inputs["compound_review.csv"]),
            )

    for row in plant_review_rows:
        if (
            normalize_whitespace(row.get("issue_type", ""))
            in EXPECTED_COMPOUND_REVIEW_ISSUES
        ):
            add_issue(
                issues,
                "plant_compound_review.csv",
                normalize_whitespace(row.get("plant_compound_review_id", "")) or "row",
                "compound_row_in_plant_review",
                "compound-level issue appeared in plant review",
                "error",
                str(inputs["plant_compound_review.csv"]),
            )

    # Warnings for small review queues / suspicious statuses
    unresolved_candidates = int(summary.get("unresolved_candidate_count", 0) or 0)
    if unresolved_candidates > 0:
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "unresolved_candidates_present",
            f"{unresolved_candidates} unresolved candidates remain",
            "warning",
            str(inputs["build_canonical_summary.json"]),
        )

    if summary.get("provisional_compounds", 0) and summary.get(
        "provisional_compounds", 0
    ) > max(1, len(compound_rows) // 2):
        add_issue(
            issues,
            "compounds.csv",
            "table",
            "high_provisional_ratio",
            "provisional compounds are unusually high",
            "warning",
            str(inputs["compounds.csv"]),
        )

    if summary.get("unmapped_plant_rows", 0) != len(plant_review_rows):
        add_issue(
            issues,
            "build_canonical_summary.json",
            "summary",
            "unmapped_plant_row_count_mismatch",
            f"summary unmapped_plant_rows={summary.get('unmapped_plant_rows')} actual plant_review_rows={len(plant_review_rows)}",
            "error",
            str(inputs["build_canonical_summary.json"]),
        )

    actual_counts = {
        "compounds_row_count": len(compound_rows),
        "candidate_map_unique_candidate_ids": len(compound_map_ids),
        "alias_row_count": len(alias_rows),
        "plant_compound_row_count": len(plant_rows),
        "compound_review_row_count": len(compound_review_rows),
        "plant_review_row_count": len(plant_review_rows),
        "candidate_member_rows": (
            len(
                read_csv_rows(
                    settings.dedupe_out_dir / "compound_candidate_members.csv"
                )[0]
            )
            if (settings.dedupe_out_dir / "compound_candidate_members.csv").exists()
            else 0
        ),
    }

    compare_summary(
        summary, actual_counts, issues, str(inputs["build_canonical_summary.json"])
    )

    # Row counts / unique counts summary
    validation_counts_rows = [
        {
            "table_name": "compounds.csv",
            "row_count": len(compound_rows),
            "unique_id_count": len(
                {
                    normalize_whitespace(r.get("compound_id", ""))
                    for r in compound_rows
                    if normalize_whitespace(r.get("compound_id", ""))
                }
            ),
            "unique_secondary_count": len(
                {
                    normalize_whitespace(r.get("canonical_key", ""))
                    for r in compound_rows
                    if normalize_whitespace(r.get("canonical_key", ""))
                }
            ),
            "issue_count": sum(1 for i in issues if i.table_name == "compounds.csv"),
            "critical_error_count": sum(
                1
                for i in issues
                if i.table_name == "compounds.csv" and i.severity == "error"
            ),
            "warning_count": sum(
                1
                for i in issues
                if i.table_name == "compounds.csv" and i.severity == "warning"
            ),
        },
        {
            "table_name": "compound_aliases.csv",
            "row_count": len(alias_rows),
            "unique_id_count": len(
                {
                    normalize_whitespace(r.get("compound_alias_id", ""))
                    for r in alias_rows
                    if normalize_whitespace(r.get("compound_alias_id", ""))
                }
            ),
            "unique_secondary_count": len(
                {
                    (
                        normalize_whitespace(r.get("compound_id", "")),
                        normalize_whitespace(r.get("alias_key", "")),
                    )
                    for r in alias_rows
                    if normalize_whitespace(r.get("compound_id", ""))
                    and normalize_whitespace(r.get("alias_key", ""))
                }
            ),
            "issue_count": sum(
                1 for i in issues if i.table_name == "compound_aliases.csv"
            ),
            "critical_error_count": sum(
                1
                for i in issues
                if i.table_name == "compound_aliases.csv" and i.severity == "error"
            ),
            "warning_count": sum(
                1
                for i in issues
                if i.table_name == "compound_aliases.csv" and i.severity == "warning"
            ),
        },
        {
            "table_name": "compound_candidate_map.csv",
            "row_count": len(candidate_map_rows),
            "unique_id_count": len(
                {
                    normalize_whitespace(r.get("compound_candidate_map_id", ""))
                    for r in candidate_map_rows
                    if normalize_whitespace(r.get("compound_candidate_map_id", ""))
                }
            ),
            "unique_secondary_count": len(
                {
                    normalize_whitespace(r.get("compound_candidate_id", ""))
                    for r in candidate_map_rows
                    if normalize_whitespace(r.get("compound_candidate_id", ""))
                }
            ),
            "issue_count": sum(
                1 for i in issues if i.table_name == "compound_candidate_map.csv"
            ),
            "critical_error_count": sum(
                1
                for i in issues
                if i.table_name == "compound_candidate_map.csv"
                and i.severity == "error"
            ),
            "warning_count": sum(
                1
                for i in issues
                if i.table_name == "compound_candidate_map.csv"
                and i.severity == "warning"
            ),
        },
        {
            "table_name": "compound_review.csv",
            "row_count": len(compound_review_rows),
            "unique_id_count": len(
                {
                    normalize_whitespace(r.get("compound_review_id", ""))
                    for r in compound_review_rows
                    if normalize_whitespace(r.get("compound_review_id", ""))
                }
            ),
            "unique_secondary_count": len(
                {
                    normalize_whitespace(r.get("compound_candidate_id", ""))
                    for r in compound_review_rows
                    if normalize_whitespace(r.get("compound_candidate_id", ""))
                }
            ),
            "issue_count": sum(
                1 for i in issues if i.table_name == "compound_review.csv"
            ),
            "critical_error_count": sum(
                1
                for i in issues
                if i.table_name == "compound_review.csv" and i.severity == "error"
            ),
            "warning_count": sum(
                1
                for i in issues
                if i.table_name == "compound_review.csv" and i.severity == "warning"
            ),
        },
        {
            "table_name": "plant_compounds.csv",
            "row_count": len(plant_rows),
            "unique_id_count": len(
                {
                    normalize_whitespace(r.get("plant_compound_id", ""))
                    for r in plant_rows
                    if normalize_whitespace(r.get("plant_compound_id", ""))
                }
            ),
            "unique_secondary_count": len(
                {
                    (
                        normalize_whitespace(r.get("plant_id", "")),
                        normalize_whitespace(r.get("compound_id", "")),
                    )
                    for r in plant_rows
                    if normalize_whitespace(r.get("plant_id", ""))
                    and normalize_whitespace(r.get("compound_id", ""))
                }
            ),
            "issue_count": sum(
                1 for i in issues if i.table_name == "plant_compounds.csv"
            ),
            "critical_error_count": sum(
                1
                for i in issues
                if i.table_name == "plant_compounds.csv" and i.severity == "error"
            ),
            "warning_count": sum(
                1
                for i in issues
                if i.table_name == "plant_compounds.csv" and i.severity == "warning"
            ),
        },
        {
            "table_name": "plant_compound_review.csv",
            "row_count": len(plant_review_rows),
            "unique_id_count": len(
                {
                    normalize_whitespace(r.get("plant_compound_review_id", ""))
                    for r in plant_review_rows
                    if normalize_whitespace(r.get("plant_compound_review_id", ""))
                }
            ),
            "unique_secondary_count": len(
                {
                    normalize_whitespace(r.get("compound_candidate_id", ""))
                    for r in plant_review_rows
                    if normalize_whitespace(r.get("compound_candidate_id", ""))
                }
            ),
            "issue_count": sum(
                1 for i in issues if i.table_name == "plant_compound_review.csv"
            ),
            "critical_error_count": sum(
                1
                for i in issues
                if i.table_name == "plant_compound_review.csv" and i.severity == "error"
            ),
            "warning_count": sum(
                1
                for i in issues
                if i.table_name == "plant_compound_review.csv"
                and i.severity == "warning"
            ),
        },
    ]

    report = {
        "module": "compounds",
        "step": "06_validate",
        "run_id": run_id,
        "settings_file": str(settings_path),
        "inputs": {name: str(path) for name, path in inputs.items()},
        "pass": not any(i.severity == "error" for i in issues),
        "critical_error_count": sum(1 for i in issues if i.severity == "error"),
        "warning_count": sum(1 for i in issues if i.severity == "warning"),
        "issue_count": len(issues),
        "issue_type_counts": dict(Counter(i.issue_type for i in issues)),
        "severity_counts": dict(Counter(i.severity for i in issues)),
        "table_counts": {row["table_name"]: row for row in validation_counts_rows},
        "summary_snapshot": summary,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "critical_errors": [
            {
                "table_name": i.table_name,
                "row_identifier": i.row_identifier,
                "issue_type": i.issue_type,
                "issue_reason": i.issue_reason,
                "source_file": i.source_file,
                "details": i.details,
            }
            for i in issues
            if i.severity == "error"
        ],
        "warnings": [
            {
                "table_name": i.table_name,
                "row_identifier": i.row_identifier,
                "issue_type": i.issue_type,
                "issue_reason": i.issue_reason,
                "source_file": i.source_file,
                "details": i.details,
            }
            for i in issues
            if i.severity == "warning"
        ],
    }

    validate_out = settings.validate_out_dir
    validate_out.mkdir(parents=True, exist_ok=True)

    issue_rows = [
        {
            "table_name": i.table_name,
            "row_identifier": i.row_identifier,
            "issue_type": i.issue_type,
            "issue_reason": i.issue_reason,
            "severity": i.severity,
            "source_file": i.source_file,
            "detail_json": json.dumps(i.details, ensure_ascii=False, sort_keys=True),
        }
        for i in sorted(
            issues,
            key=lambda x: (
                x.severity,
                x.table_name,
                x.row_identifier,
                x.issue_type,
                x.issue_reason,
            ),
        )
    ]

    validation_counts_csv_rows = validation_counts_rows

    # validated pass-through copies (stable ordering, no mutation)
    validated_compounds = stable_sort_rows(
        compound_rows, ["compound_id", "canonical_key"]
    )
    validated_aliases = stable_sort_rows(
        alias_rows, ["compound_id", "alias_key", "alias_type"]
    )
    validated_candidate_map = stable_sort_rows(
        candidate_map_rows, ["compound_candidate_id"]
    )
    validated_compound_review = stable_sort_rows(
        compound_review_rows, ["compound_review_id"]
    )
    validated_plant_compounds = stable_sort_rows(
        plant_rows, ["plant_id", "compound_id"]
    )
    validated_plant_review = stable_sort_rows(
        plant_review_rows, ["plant_compound_review_id"]
    )

    write_json(
        validate_out / "validation_report.json",
        report,
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validation_issues.csv",
        issue_rows,
        [
            "table_name",
            "row_identifier",
            "issue_type",
            "issue_reason",
            "severity",
            "source_file",
            "detail_json",
        ],
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validation_counts.csv",
        validation_counts_csv_rows,
        [
            "table_name",
            "row_count",
            "unique_id_count",
            "unique_secondary_count",
            "issue_count",
            "critical_error_count",
            "warning_count",
        ],
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validated_compounds.csv",
        validated_compounds,
        COMPOUNDS_COLUMNS,
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validated_compound_aliases.csv",
        validated_aliases,
        ALIASES_COLUMNS,
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validated_compound_candidate_map.csv",
        validated_candidate_map,
        CANDIDATE_MAP_COLUMNS,
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validated_compound_review.csv",
        validated_compound_review,
        COMPOUND_REVIEW_COLUMNS,
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validated_plant_compounds.csv",
        validated_plant_compounds,
        PLANT_COMPOUNDS_COLUMNS,
        overwrite=settings.overwrite_outputs,
    )
    write_csv(
        validate_out / "validated_plant_compound_review.csv",
        validated_plant_review,
        PLANT_REVIEW_COLUMNS,
        overwrite=settings.overwrite_outputs,
    )

    logger.info("Validation pass: %s", report["pass"])
    logger.info("Critical errors: %d", report["critical_error_count"])
    logger.info("Warnings: %d", report["warning_count"])
    logger.info("Validation report: %s", validate_out / "validation_report.json")
    logger.info("Validation issues: %s", validate_out / "validation_issues.csv")
    logger.info("Validation counts: %s", validate_out / "validation_counts.csv")
    logger.info("Log file: %s", log_path)

    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
