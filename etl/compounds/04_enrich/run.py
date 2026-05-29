"""Enrich deduplicated compound candidates with stable chemical identity data.

Purpose
-------
This script is the enrichment step of the compound ETL pipeline. It consumes the
deduplicated compound candidate output from `03_dedupe_candidates`, queries stable
chemical sources (PubChem and ChEMBL), caches all request/response payloads locally,
scores candidate matches deterministically, and writes one enrichment row per unique
compound candidate.

Inputs
------
- `compounds/03_dedupe_candidates/out/compound_candidates.csv`
- `compounds/03_dedupe_candidates/out/compound_candidate_members.csv`
- `compounds/03_dedupe_candidates/out/compound_candidate_review.csv`
- Settings from `settings.yml`

Outputs
-------
Written only to `compounds/04_enrich/out/`:
- `compound_enrichment_results.csv`
- `compound_enrichment_cache.csv`
- `compound_enrichment_member_map.csv`
- `compound_enrichment_review.csv`
- `enrich_summary.json`
- log file in `out/logs/`
- cached API payloads in `out/cache/`

Behavior
--------
- Enriches one row per unique compound candidate, not one row per raw plant-compound
  evidence row.
- Uses candidate-level search payloads built from representative fields plus all
  supporting member evidence.
- Searches PubChem and ChEMBL with deterministic, cache-first behavior.
- Preserves review rows and slightly malformed CAS values as search evidence.
- Does not create final canonical compound IDs.
- Does not build final `compounds.csv` here.
- Does not use SwissADME, SwissTargetPrediction, or docking.
- Is idempotent and safe to rerun with the same inputs and settings.

Downstream contract
-------------------
`05_build_canonical` should consume the enrichment results together with candidate
member mappings so enriched identifiers can be propagated back to all evidence rows.
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings as shared_load_settings, ensure_dir, normalize_whitespace, make_run_id, now_iso

import argparse
import csv
import hashlib
import json
import logging
import math
import os
import re
import socket
import threading
import time
import random
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
from http.client import RemoteDisconnected
from collections import defaultdict


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

MEMBER_COLUMNS = [
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

REVIEW_COLUMNS = [
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

RESULT_COLUMNS = [
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
    "tpsa",
    "logp",
    "hbond_donors",
    "hbond_acceptors",
    "rotatable_bonds",
    "qed_score",
    "np_likeness_score",
    "num_ro5_violations",
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
]

CACHE_INDEX_COLUMNS = [
    "cache_key",
    "compound_candidate_id",
    "candidate_key",
    "candidate_status",
    "cache_hit",
    "request_count",
    "request_cache_hits",
    "request_cache_misses",
    "selected_source_name",
    "selected_identifier",
    "selected_inchi_key",
    "selected_pubchem_cid",
    "selected_chembl_id",
    "enrichment_confidence",
    "cache_file",
    "search_terms_json",
    "created_at",
]

MEMBER_MAP_COLUMNS = [
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


@dataclass(frozen=True)
class Settings:
    module_root: Path
    dedupe_out_dir: Path
    enrich_out_dir: Path
    enrich_log_dir: Path
    cache_root: Path
    candidate_input_file: Path
    member_input_file: Path
    review_input_file: Path
    source_name: str
    source_url: str
    batch_id: str
    run_id_prefix: str
    timestamp_format: str
    overwrite_outputs: bool
    write_summary_json: bool
    min_auto_accept_confidence: float
    high_confidence_threshold: float
    medium_confidence_threshold: float
    pubchem_cfg: Dict[str, Any]
    chembl_cfg: Dict[str, Any]
    cache_responses: bool
    request_delay_seconds: float
    max_retries: int
    timeout_seconds: int
    max_pubchem_cids: int
    max_chembl_hits: int
    max_terms_per_source: int


@dataclass(frozen=True)
class SearchTerm:
    text: str
    kind: str  # cas | name | formula | mw
    priority: int
    provenance: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class SourceHit:
    source_name: str
    identifier: str
    source_url: str
    pubchem_cid: str = ""
    chembl_id: str = ""
    inchi_key: str = ""
    smiles: str = ""
    molecular_formula: str = ""
    molecular_weight: str = ""
    tpsa: str = ""
    logp: str = ""
    hbond_donors: str = ""
    hbond_acceptors: str = ""
    rotatable_bonds: str = ""
    qed_score: str = ""
    np_likeness_score: str = ""
    num_ro5_violations: str = ""
    iupac_name: str = ""
    preferred_name: str = ""
    synonyms: Tuple[str, ...] = ()
    match_score: float = 0.0
    match_reason: str = ""
    matched_term: str = ""
    matched_term_kind: str = ""
    query_count: int = 0
    extra: Dict[str, Any] = None


# normalize_whitespace imported from shared.utils


def normalize_key(value: Optional[str]) -> str:
    text = normalize_whitespace(value).strip().lower()
    if not text:
        return ""
    text = re.sub(r"[\u2010-\u2015]", "-", text)
    text = re.sub(r"[^a-z0-9]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text


def normalize_formula(value: Optional[str]) -> str:
    text = normalize_whitespace(value)
    if not text:
        return ""
    return text.replace(" ", "")


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


def format_number(value: Optional[str]) -> str:
    num = parse_float(value)
    if num is None:
        return ""
    out = f"{num:.6f}".rstrip("0").rstrip(".")
    return out if out else "0"


def is_cas_like(value: str) -> bool:
    text = normalize_whitespace(value)
    return bool(re.fullmatch(r"\d{1,7}-\d{1,2}-[\dXx]", text))


def is_formula_like(value: str) -> bool:
    text = normalize_whitespace(value)
    if not text or " " in text:
        return False
    if not re.fullmatch(r"[A-Za-z0-9().·+\-]+", text):
        return False
    has_letter = any(ch.isalpha() for ch in text)
    has_digit = any(ch.isdigit() for ch in text)
    return has_letter and has_digit and len(text) <= 80


def is_mw_like(value: str) -> bool:
    text = normalize_whitespace(value)
    if not text:
        return False
    try:
        num = float(text)
    except ValueError:
        return False
    return 1.0 <= num <= 5000.0


def stable_hash(payload: Dict[str, Any]) -> str:
    canonical_json = json.dumps(
        payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def stable_timestamp(batch_id: str) -> str:
    if batch_id and batch_id != "auto":
        return batch_id
    return datetime.now(timezone.utc).isoformat()


def safe_load_json(
    path: Path, logger: Optional[logging.Logger] = None
) -> Optional[Any]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except (json.JSONDecodeError, OSError) as exc:
        if logger is not None:
            logger.warning("Ignoring unreadable JSON cache file %s: %s", path, exc)
        return None


_CACHE_WRITE_LOCKS: dict[str, threading.Lock] = defaultdict(threading.Lock)
_CACHE_LOCK_GUARD = threading.Lock()


def _lock_for_path(path: Path) -> threading.Lock:
    key = str(path.resolve())
    with _CACHE_LOCK_GUARD:
        return _CACHE_WRITE_LOCKS[key]


def atomic_write_json(path: Path, payload: Dict[str, Any], *, retries: int = 5) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")

    lock = _lock_for_path(path)
    with lock:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())

        last_exc: Optional[BaseException] = None
        for attempt in range(retries + 1):
            try:
                os.replace(tmp_path, path)
                return
            except PermissionError as exc:
                last_exc = exc
                if attempt >= retries:
                    break
                time.sleep(0.05 * (2**attempt) + random.uniform(0.0, 0.05))

        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass
        raise last_exc  # type: ignore[misc]


def configure_logging(log_dir: Path, run_id: str) -> Path:
    ensure_dir(log_dir)
    log_path = log_dir / f"enrich_compounds_{run_id}.log"

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


def load_settings_for_enrich() -> Settings:
    config = shared_load_settings("compounds")

    paths_cfg = config.get("paths", {})
    step_dirs_cfg = paths_cfg.get("step_dirs", {})
    source_cfg = config.get("source", {})
    enrichment_cfg = config.get("enrichment", {})
    validation_cfg = config.get("validation", {})
    thresholds_cfg = validation_cfg.get("thresholds", {})

    dedupe_out_dir = ETL_ROOT / step_dirs_cfg["dedupe_candidates_out"]
    enrich_out_dir = ETL_ROOT / step_dirs_cfg["enrich_out"]
    enrich_log_dir = enrich_out_dir / "logs"
    cache_root = enrich_out_dir / "cache"

    candidate_input = dedupe_out_dir / "compound_candidates.csv"
    member_input = dedupe_out_dir / "compound_candidate_members.csv"
    review_input = dedupe_out_dir / "compound_candidate_review.csv"

    pubchem_cfg = enrichment_cfg.get("pubchem", {})
    chembl_cfg = enrichment_cfg.get("chembl", {})

    return Settings(
        module_root=ETL_ROOT / "compounds",
        dedupe_out_dir=dedupe_out_dir,
        enrich_out_dir=enrich_out_dir,
        enrich_log_dir=enrich_log_dir,
        cache_root=cache_root,
        candidate_input_file=candidate_input,
        member_input_file=member_input,
        review_input_file=review_input,
        source_name=str(source_cfg.get("name", "KNApSAcK")),
        source_url=str(source_cfg.get("url", "")),
        batch_id=str(source_cfg.get("batch_id", "auto")),
        run_id_prefix="compounds",
        timestamp_format="%Y%m%d_%H%M%S",
        overwrite_outputs=False,
        write_summary_json=True,
        min_auto_accept_confidence=float(
            thresholds_cfg.get("min_compound_confidence_to_auto_accept", 0.70)
        ),
        high_confidence_threshold=float(
            config.get("matching", {}).get("high_confidence_threshold", 0.90)
        ),
        medium_confidence_threshold=float(
            config.get("matching", {}).get("medium_confidence_threshold", 0.70)
        ),
        pubchem_cfg=pubchem_cfg,
        chembl_cfg=chembl_cfg,
        cache_responses=bool(pubchem_cfg.get("cache_responses", True)),
        request_delay_seconds=float(pubchem_cfg.get("request_delay_seconds", 0.3)),
        max_retries=int(pubchem_cfg.get("max_retries", 4)),
        timeout_seconds=int(pubchem_cfg.get("timeout_seconds", 30)),
        max_pubchem_cids=int(pubchem_cfg.get("max_cids", 10)),
        max_chembl_hits=int(chembl_cfg.get("max_hits", 10)),
        max_terms_per_source=int(enrichment_cfg.get("max_terms_per_source", 8)),
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


def load_candidate_inputs(
    settings: Settings,
) -> Tuple[
    List[Dict[str, str]], Dict[str, List[Dict[str, str]]], Dict[str, Dict[str, str]]
]:
    if not settings.candidate_input_file.exists():
        raise FileNotFoundError(
            f"Candidate input file not found: {settings.candidate_input_file}"
        )

    candidate_rows, candidate_fields = read_csv_rows(settings.candidate_input_file)
    ensure_columns(candidate_fields, CANDIDATE_COLUMNS, "compound_candidates.csv")

    member_rows, member_fields = read_csv_rows(settings.member_input_file)
    ensure_columns(member_fields, MEMBER_COLUMNS, "compound_candidate_members.csv")

    review_rows: List[Dict[str, str]] = []
    if settings.review_input_file.exists():
        review_rows, review_fields = read_csv_rows(settings.review_input_file)
        ensure_columns(review_fields, [], "compound_candidate_review.csv")

    members_by_candidate: Dict[str, List[Dict[str, str]]] = {}
    for row in member_rows:
        cid = normalize_whitespace(row.get("compound_candidate_id", ""))
        if not cid:
            continue
        members_by_candidate.setdefault(cid, []).append(row)

    review_by_candidate: Dict[str, Dict[str, str]] = {}
    for row in review_rows:
        cid = normalize_whitespace(row.get("compound_candidate_id", ""))
        if cid:
            review_by_candidate[cid] = row

    return candidate_rows, members_by_candidate, review_by_candidate


def collect_search_terms(
    candidate: Dict[str, str], members: List[Dict[str, str]], max_terms: int
) -> List[SearchTerm]:
    terms: List[SearchTerm] = []
    seen: set[Tuple[str, str]] = set()

    def add_term(
        text: Optional[str], kind: str, priority: int, provenance: str
    ) -> None:
        raw = normalize_whitespace(text)
        if not raw:
            return
        key = (kind, normalize_key(raw))
        if key in seen:
            return
        seen.add(key)
        terms.append(
            SearchTerm(text=raw, kind=kind, priority=priority, provenance=provenance)
        )

    # Candidate representative fields first.
    add_term(
        candidate.get("representative_cas_id"),
        "cas",
        1,
        "candidate.representative_cas_id",
    )
    add_term(
        candidate.get("representative_name"), "name", 2, "candidate.representative_name"
    )
    add_term(
        candidate.get("representative_formula"),
        "formula",
        3,
        "candidate.representative_formula",
    )
    add_term(candidate.get("representative_mw"), "mw", 4, "candidate.representative_mw")

    # Then supporting member evidence, preserving review rows as search evidence.
    for member in members:
        add_term(
            member.get("normalized_cas_id"),
            "cas",
            1,
            f"member:{member.get('compound_candidate_member_id','')}:normalized_cas_id",
        )
        add_term(
            member.get("cas_id"),
            "cas",
            1,
            f"member:{member.get('compound_candidate_member_id','')}:cas_id",
        )
        add_term(
            member.get("normalized_metabolite_name"),
            "name",
            2,
            f"member:{member.get('compound_candidate_member_id','')}:normalized_metabolite_name",
        )
        add_term(
            member.get("metabolite"),
            "name",
            2,
            f"member:{member.get('compound_candidate_member_id','')}:metabolite",
        )
        add_term(
            member.get("normalized_formula"),
            "formula",
            3,
            f"member:{member.get('compound_candidate_member_id','')}:normalized_formula",
        )
        add_term(
            member.get("molecular_formula"),
            "formula",
            3,
            f"member:{member.get('compound_candidate_member_id','')}:molecular_formula",
        )
        add_term(
            member.get("normalized_mw"),
            "mw",
            4,
            f"member:{member.get('compound_candidate_member_id','')}:normalized_mw",
        )
        add_term(
            member.get("mw"),
            "mw",
            4,
            f"member:{member.get('compound_candidate_member_id','')}:mw",
        )

    terms.sort(key=lambda t: (t.priority, t.kind, normalize_key(t.text), t.provenance))
    return terms[:max_terms]


def candidate_search_payload(
    candidate: Dict[str, str],
    members: List[Dict[str, str]],
    terms: List[SearchTerm],
    settings: Settings,
) -> Dict[str, Any]:
    member_hashes = sorted(
        normalize_whitespace(
            m.get("normalized_source_row_id")
            or m.get("source_row_hash")
            or m.get("raw_row_hash")
            or m.get("source_compound_key")
            or ""
        )
        for m in members
    )
    payload = {
        "candidate_id": candidate.get("compound_candidate_id", ""),
        "candidate_key": candidate.get("candidate_key", ""),
        "candidate_key_strategy": candidate.get("candidate_key_strategy", ""),
        "representative_name": candidate.get("representative_name", ""),
        "representative_cas_id": candidate.get("representative_cas_id", ""),
        "representative_formula": candidate.get("representative_formula", ""),
        "representative_mw": candidate.get("representative_mw", ""),
        "search_terms": [t.to_dict() for t in terms],
        "member_source_rows": member_hashes,
        "source_name": settings.source_name,
        "source_url": settings.source_url,
        "pubchem_base_url": settings.pubchem_cfg.get(
            "base_url", "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
        ),
        "chembl_base_url": settings.chembl_cfg.get(
            "base_url", "https://www.ebi.ac.uk/chembl/api/data"
        ),
        "thresholds": {
            "high": settings.high_confidence_threshold,
            "medium": settings.medium_confidence_threshold,
            "auto_accept": settings.min_auto_accept_confidence,
        },
    }
    return payload


def candidate_cache_key(payload: Dict[str, Any]) -> str:
    return stable_hash(payload)


def request_cache_path(cache_root: Path, source: str, url: str) -> Path:
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()
    return cache_root / "http" / source / f"{digest}.json"


def candidate_cache_path(cache_root: Path, cache_key: str) -> Path:
    return cache_root / "candidates" / f"{cache_key}.json"


def cached_get_json(
    url: str,
    cache_path: Path,
    timeout: int,
    retries: int,
    delay_seconds: float,
    source_name: str,
    cache_enabled: bool,
    logger: logging.Logger,
) -> Tuple[Dict[str, Any], bool]:
    if cache_enabled and cache_path.exists():
        cached = safe_load_json(cache_path, logger)
        if cached is not None:
            return cached, True

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    last_error: Optional[str] = None
    for attempt in range(retries + 1):
        if attempt > 0:
            sleep_for = delay_seconds * (2 ** (attempt - 1))
            time.sleep(sleep_for)
        try:
            req = Request(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (compound-etl/1.0)",
                    "Accept": "application/json,text/plain,*/*",
                },
            )
            with urlopen(req, timeout=timeout) as resp:
                status_code = getattr(resp, "status", resp.getcode())
                body = resp.read().decode("utf-8", errors="replace")
                try:
                    parsed = json.loads(body)
                except json.JSONDecodeError:
                    parsed = None
                record = {
                    "ok": 200 <= int(status_code) < 300,
                    "source_name": source_name,
                    "url": url,
                    "status_code": int(status_code),
                    "retrieved_at": datetime.now(timezone.utc).isoformat(),
                    "response_text": body,
                    "response_json": parsed,
                    "error": "",
                }
                if cache_enabled:
                    atomic_write_json(cache_path, record)
                return record, False
        except HTTPError as exc:
            body = ""
            try:
                body = exc.read().decode("utf-8", errors="replace")
            except Exception:
                body = ""
            last_error = f"HTTPError {exc.code}: {exc.reason}"
            logger.warning(
                "Request failed (%s) attempt=%d url=%s", last_error, attempt + 1, url
            )
            if exc.code in {429, 500, 502, 503, 504} and attempt < retries:
                continue
            record = {
                "ok": False,
                "source_name": source_name,
                "url": url,
                "status_code": int(exc.code),
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "response_text": body,
                "response_json": None,
                "error": last_error,
            }
            if cache_enabled:
                atomic_write_json(cache_path, record)
            return record, False
        except (
            RemoteDisconnected,
            TimeoutError,
            socket.timeout,
            ConnectionResetError,
            URLError,
        ) as exc:
            if isinstance(exc, URLError):
                reason = getattr(exc, "reason", exc)
                last_error = f"URLError: {reason}"
            elif isinstance(exc, RemoteDisconnected):
                last_error = f"RemoteDisconnected: {exc}"
            elif isinstance(exc, socket.timeout):
                last_error = f"socket.timeout: {exc}"
            elif isinstance(exc, TimeoutError):
                last_error = f"TimeoutError: {exc}"
            else:
                last_error = f"{type(exc).__name__}: {exc}"
            logger.warning(
                "Request failed (%s) attempt=%d url=%s", last_error, attempt + 1, url
            )
            if attempt < retries:
                continue
            record = {
                "ok": False,
                "source_name": source_name,
                "url": url,
                "status_code": 0,
                "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "response_text": "",
                "response_json": None,
                "error": last_error,
            }
            if cache_enabled:
                atomic_write_json(cache_path, record)
            return record, False
    record = {
        "ok": False,
        "source_name": source_name,
        "url": url,
        "status_code": 0,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "response_text": "",
        "response_json": None,
        "error": last_error or "unknown error",
    }
    if cache_enabled:
        atomic_write_json(cache_path, record)
    return record, False


def pubchem_search_url(base_url: str, term: str, kind: str) -> str:
    segment = quote(term, safe="")
    if kind == "formula":
        return f"{base_url}/compound/formula/{segment}/cids/JSON"
    return f"{base_url}/compound/name/{segment}/cids/JSON"


def pubchem_properties_url(base_url: str, cid: str) -> str:
    props = "IUPACName,CanonicalSMILES,IsomericSMILES,InChIKey,MolecularFormula,MolecularWeight,Title"
    return f"{base_url}/compound/cid/{quote(str(cid), safe='')}/property/{props}/JSON"


def pubchem_synonyms_url(base_url: str, cid: str) -> str:
    return f"{base_url}/compound/cid/{quote(str(cid), safe='')}/synonyms/JSON"


def chembl_search_url(base_url: str, term: str) -> str:
    params = urlencode({"q": term, "limit": 20})
    return f"{base_url}/molecule/search.json?{params}"


def chembl_detail_url(base_url: str, chembl_id: str) -> str:
    return f"{base_url}/molecule/{quote(chembl_id, safe='')}.json"


def extract_pubchem_cids(payload: Dict[str, Any]) -> List[str]:
    if not payload:
        return []
    for key_path in [
        ("IdentifierList", "CID"),
        ("IdentifierList", "CIDs"),
    ]:
        node = payload
        ok = True
        for key in key_path:
            if not isinstance(node, dict) or key not in node:
                ok = False
                break
            node = node[key]
        if ok and isinstance(node, list):
            return [str(x) for x in node]
    return []


def extract_pubchem_properties(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        return []
    table = payload.get("PropertyTable", {})
    props = table.get("Properties", [])
    return props if isinstance(props, list) else []


def extract_pubchem_synonyms(payload: Dict[str, Any]) -> List[str]:
    if not payload:
        return []
    info = payload.get("InformationList", {})
    infolist = info.get("Information", [])
    if not infolist:
        return []
    first = infolist[0]
    syn = first.get("Synonym", []) or first.get("Synonyms", [])
    if isinstance(syn, list):
        return [normalize_whitespace(x) for x in syn if normalize_whitespace(x)]
    return []


def extract_chembl_molecules(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    if not payload:
        return []
    for key in ["molecules", "molecule", "molecule_search_results"]:
        if key in payload and isinstance(payload[key], list):
            return payload[key]
    return []


def chembl_pref_name(mol: Dict[str, Any]) -> str:
    return normalize_whitespace(
        mol.get("pref_name")
        or mol.get("preferred_name")
        or mol.get("molecule_name")
        or ""
    )


def chembl_synonyms(mol: Dict[str, Any]) -> List[str]:
    syns: List[str] = []
    raw = mol.get("molecule_synonyms") or mol.get("synonyms") or []
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict):
                syn = normalize_whitespace(
                    item.get("synonym")
                    or item.get("synonyms")
                    or item.get("value")
                    or ""
                )
                if syn:
                    syns.append(syn)
            else:
                syn = normalize_whitespace(item)
                if syn:
                    syns.append(syn)
    return syns


def chembl_structures(mol: Dict[str, Any]) -> Dict[str, str]:
    structures = mol.get("molecule_structures") or {}
    if not isinstance(structures, dict):
        structures = {}
    return {
        "inchi_key": normalize_whitespace(
            structures.get("standard_inchi_key")
            or structures.get("standard_inchi")
            or structures.get("inchi_key")
            or ""
        ),
        "smiles": normalize_whitespace(
            structures.get("canonical_smiles")
            or structures.get("molecule_smiles")
            or structures.get("smiles")
            or ""
        ),
    }


def chembl_properties(mol: Dict[str, Any]) -> Dict[str, str]:
    props = mol.get("molecule_properties") or {}
    if not isinstance(props, dict):
        props = {}

    def _s(val: Any) -> str:
        v = val if val is not None else ""
        return normalize_whitespace(str(v)) if v != "" else ""

    return {
        "molecular_formula": _s(props.get("full_molformula") or props.get("molecular_formula")),
        "molecular_weight": _s(
            props.get("full_mwt") or props.get("mw_freebase") or props.get("molecular_weight")
        ),
        "tpsa": _s(props.get("psa")),
        "logp": _s(props.get("alogp")),
        "hbond_donors": _s(props.get("hbd")),
        "hbond_acceptors": _s(props.get("hba")),
        "rotatable_bonds": _s(props.get("rtb")),
        "qed_score": _s(props.get("qed_weighted")),
        "np_likeness_score": _s(props.get("np_likeness_score")),
        "num_ro5_violations": _s(props.get("num_ro5_violations")),
    }


def build_term_match_score(term: SearchTerm, hit: SourceHit) -> Tuple[float, str]:
    term_text = normalize_whitespace(term.text)
    term_key = normalize_key(term_text)
    hit_name_keys = {
        normalize_key(hit.preferred_name),
        normalize_key(hit.iupac_name),
        *(normalize_key(s) for s in hit.synonyms),
    }
    hit_formula_key = normalize_key(hit.molecular_formula)
    hit_mw = parse_float(hit.molecular_weight)

    reasons: List[str] = []

    if term.kind == "cas":
        if term_key and term_key in hit_name_keys:
            return 0.97, "exact_cas_or_synonym"
        if term_text and any(
            normalize_whitespace(s) == term_text for s in hit.synonyms
        ):
            return 0.98, "exact_cas_synonym"
        if term_key and term_key == normalize_key(hit.preferred_name):
            return 0.92, "cas_as_name"
        if term_key and term_key == normalize_key(hit.iupac_name):
            return 0.90, "cas_as_iupac_name"
        if term_key and term_key in hit_name_keys:
            return 0.88, "cas_synonym_match"
        return 0.25, "cas_no_direct_match"

    if term.kind == "name":
        if term_key and term_key == normalize_key(hit.preferred_name):
            return 0.94, "exact_name_match"
        if term_key and term_key == normalize_key(hit.iupac_name):
            return 0.92, "exact_iupac_match"
        if term_key and term_key in hit_name_keys:
            return 0.88, "synonym_name_match"
        if term_key and any(term_key in k or k in term_key for k in hit_name_keys if k):
            return 0.78, "fuzzy_name_overlap"
        return 0.30, "name_no_direct_match"

    if term.kind == "formula":
        if term_key and term_key == hit_formula_key:
            return 0.90, "exact_formula_match"
        if term_key and term_key and term_key in hit_formula_key:
            return 0.70, "formula_substring_match"
        return 0.20, "formula_no_direct_match"

    if term.kind == "mw":
        term_num = parse_float(term_text)
        if term_num is None or hit_mw is None:
            return 0.15, "mw_unusable"
        delta = abs(term_num - hit_mw)
        rel = delta / max(term_num, hit_mw, 1.0)
        if rel <= 0.005:
            return 0.82, "mw_near_exact"
        if rel <= 0.01:
            return 0.70, "mw_close"
        if rel <= 0.02:
            return 0.55, "mw_approximate"
        return 0.20, "mw_far"

    reasons.append("unknown_term_kind")
    return 0.10, ";".join(reasons)


def score_hit(
    hit: SourceHit, terms: List[SearchTerm], candidate: Dict[str, str]
) -> SourceHit:
    best_score = 0.0
    best_reason = ""
    best_term = ""
    best_kind = ""
    matched_kinds: set[str] = set()

    for term in terms:
        score, reason = build_term_match_score(term, hit)
        if score > best_score:
            best_score = score
            best_reason = reason
            best_term = term.text
            best_kind = term.kind
        if score >= 0.80:
            matched_kinds.add(term.kind)

    # Cross-field support bonuses
    if hit.inchi_key and hit.inchi_key and best_score >= 0.80:
        best_score += 0.03
        best_reason += ";inchi_supported"
    if {"name", "formula"}.issubset(matched_kinds):
        best_score += 0.04
        best_reason += ";name_formula_support"
    if {"cas", "name"}.issubset(matched_kinds):
        best_score += 0.05
        best_reason += ";cas_name_support"
    if {"cas", "formula"}.issubset(matched_kinds):
        best_score += 0.03
        best_reason += ";cas_formula_support"

    # MW agreement bonus when available.
    candidate_mw = parse_float(candidate.get("representative_mw", ""))
    hit_mw = parse_float(hit.molecular_weight)
    if candidate_mw is not None and hit_mw is not None:
        rel = abs(candidate_mw - hit_mw) / max(candidate_mw, hit_mw, 1.0)
        if rel <= 0.01:
            best_score += 0.03
            best_reason += ";mw_support"

    best_score = min(0.99, best_score)
    hit.match_score = best_score
    hit.match_reason = best_reason
    hit.matched_term = best_term
    hit.matched_term_kind = best_kind
    return hit


def pubchem_hit_from_properties(
    cid: str,
    prop: Dict[str, Any],
    synonyms: List[str],
    query_count: int,
    source_url: str,
) -> SourceHit:
    return SourceHit(
        source_name="PubChem",
        identifier=str(cid),
        source_url=source_url,
        pubchem_cid=str(cid),
        chembl_id="",
        inchi_key=normalize_whitespace(prop.get("InChIKey") or ""),
        smiles=normalize_whitespace(
            prop.get("CanonicalSMILES") or prop.get("IsomericSMILES") or ""
        ),
        molecular_formula=normalize_whitespace(prop.get("MolecularFormula") or ""),
        molecular_weight=normalize_whitespace(prop.get("MolecularWeight") or ""),
        iupac_name=normalize_whitespace(prop.get("IUPACName") or ""),
        preferred_name=normalize_whitespace(
            prop.get("Title")
            or prop.get("IUPACName")
            or prop.get("CanonicalSMILES")
            or ""
        ),
        synonyms=tuple(
            normalize_whitespace(s) for s in synonyms if normalize_whitespace(s)
        ),
        query_count=query_count,
        extra={"source": "PubChem"},
    )


def chembl_hit_from_detail(
    detail: Dict[str, Any], query_count: int, source_url: str
) -> SourceHit:
    structures = chembl_structures(detail)
    props = chembl_properties(detail)
    pref = chembl_pref_name(detail)
    syns = chembl_synonyms(detail)
    chembl_id = normalize_whitespace(
        detail.get("molecule_chembl_id") or detail.get("chembl_id") or ""
    )
    return SourceHit(
        source_name="ChEMBL",
        identifier=chembl_id or source_url,
        source_url=source_url,
        pubchem_cid="",
        chembl_id=chembl_id,
        inchi_key=structures["inchi_key"],
        smiles=structures["smiles"],
        molecular_formula=props["molecular_formula"],
        molecular_weight=props["molecular_weight"],
        tpsa=props["tpsa"],
        logp=props["logp"],
        hbond_donors=props["hbond_donors"],
        hbond_acceptors=props["hbond_acceptors"],
        rotatable_bonds=props["rotatable_bonds"],
        qed_score=props["qed_score"],
        np_likeness_score=props["np_likeness_score"],
        num_ro5_violations=props["num_ro5_violations"],
        iupac_name=normalize_whitespace(
            detail.get("molecule_name") or detail.get("pref_name") or pref
        ),
        preferred_name=pref or normalize_whitespace(detail.get("molecule_name") or ""),
        synonyms=tuple(syns),
        query_count=query_count,
        extra={"source": "ChEMBL"},
    )


def search_pubchem(
    candidate: Dict[str, str],
    terms: List[SearchTerm],
    settings: Settings,
    logger: logging.Logger,
    request_cache_dir: Path,
) -> Tuple[List[SourceHit], Dict[str, Any]]:
    base_url = settings.pubchem_cfg.get(
        "base_url", "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    )
    hits: List[SourceHit] = []
    request_meta: List[Dict[str, Any]] = []
    term_count = 0

    # Prefer name/CAS/formula searches; MW is used as weak evidence, not a direct query.
    for term in terms:
        if term.kind == "mw":
            continue
        if term_count >= settings.max_terms_per_source:
            break
        term_count += 1

        url = pubchem_search_url(base_url, term.text, term.kind)
        cache_path = request_cache_path(settings.cache_root, "pubchem", url)
        record, cache_hit = cached_get_json(
            url,
            cache_path,
            timeout=settings.timeout_seconds,
            retries=settings.max_retries,
            delay_seconds=settings.request_delay_seconds,
            source_name="PubChem",
            cache_enabled=settings.cache_responses,
            logger=logger,
        )
        request_meta.append(
            {
                "url": url,
                "cache_hit": cache_hit,
                "status_code": record.get("status_code", 0),
                "ok": record.get("ok", False),
                "error": record.get("error", ""),
                "cache_path": str(cache_path),
                "term": term.to_dict(),
            }
        )
        if not record.get("ok"):
            continue

        cids = extract_pubchem_cids(record.get("response_json") or {})
        if not cids:
            continue

        for cid in cids[: settings.max_pubchem_cids]:
            detail_url = pubchem_properties_url(base_url, cid)
            detail_cache = request_cache_path(
                settings.cache_root, "pubchem", detail_url
            )
            detail_record, detail_cache_hit = cached_get_json(
                detail_url,
                detail_cache,
                timeout=settings.timeout_seconds,
                retries=settings.max_retries,
                delay_seconds=settings.request_delay_seconds,
                source_name="PubChem",
                cache_enabled=settings.cache_responses,
                logger=logger,
            )
            request_meta.append(
                {
                    "url": detail_url,
                    "cache_hit": detail_cache_hit,
                    "status_code": detail_record.get("status_code", 0),
                    "ok": detail_record.get("ok", False),
                    "error": detail_record.get("error", ""),
                    "cache_path": str(detail_cache),
                    "term": term.to_dict(),
                    "detail": True,
                }
            )
            if not detail_record.get("ok"):
                continue

            props = extract_pubchem_properties(detail_record.get("response_json") or {})
            if not props:
                continue
            prop = props[0]

            syn_url = pubchem_synonyms_url(base_url, cid)
            syn_cache = request_cache_path(settings.cache_root, "pubchem", syn_url)
            syn_record, syn_cache_hit = cached_get_json(
                syn_url,
                syn_cache,
                timeout=settings.timeout_seconds,
                retries=settings.max_retries,
                delay_seconds=settings.request_delay_seconds,
                source_name="PubChem",
                cache_enabled=settings.cache_responses,
                logger=logger,
            )
            request_meta.append(
                {
                    "url": syn_url,
                    "cache_hit": syn_cache_hit,
                    "status_code": syn_record.get("status_code", 0),
                    "ok": syn_record.get("ok", False),
                    "error": syn_record.get("error", ""),
                    "cache_path": str(syn_cache),
                    "term": term.to_dict(),
                    "synonyms": True,
                }
            )
            syns = (
                extract_pubchem_synonyms(syn_record.get("response_json") or {})
                if syn_record.get("ok")
                else []
            )

            hit = pubchem_hit_from_properties(
                cid=str(cid),
                prop=prop,
                synonyms=syns,
                query_count=1,
                source_url=f"https://pubchem.ncbi.nlm.nih.gov/compound/{cid}",
            )
            hit = score_hit(hit, terms, candidate)
            hits.append(hit)

    return hits, {"source": "PubChem", "requests": request_meta}


def search_chembl(
    candidate: Dict[str, str],
    terms: List[SearchTerm],
    settings: Settings,
    logger: logging.Logger,
    request_cache_dir: Path,
) -> Tuple[List[SourceHit], Dict[str, Any]]:
    base_url = settings.chembl_cfg.get(
        "base_url", "https://www.ebi.ac.uk/chembl/api/data"
    )
    hits: List[SourceHit] = []
    request_meta: List[Dict[str, Any]] = []
    term_count = 0

    for term in terms:
        if term.kind == "mw":
            continue
        if term_count >= settings.max_terms_per_source:
            break
        term_count += 1

        url = chembl_search_url(base_url, term.text)
        cache_path = request_cache_path(settings.cache_root, "chembl", url)
        record, cache_hit = cached_get_json(
            url,
            cache_path,
            timeout=settings.timeout_seconds,
            retries=settings.max_retries,
            delay_seconds=settings.request_delay_seconds,
            source_name="ChEMBL",
            cache_enabled=settings.cache_responses,
            logger=logger,
        )
        request_meta.append(
            {
                "url": url,
                "cache_hit": cache_hit,
                "status_code": record.get("status_code", 0),
                "ok": record.get("ok", False),
                "error": record.get("error", ""),
                "cache_path": str(cache_path),
                "term": term.to_dict(),
            }
        )
        if not record.get("ok"):
            continue

        molecules = extract_chembl_molecules(record.get("response_json") or {})
        if not molecules:
            continue

        for mol in molecules[: settings.max_chembl_hits]:
            chembl_id = normalize_whitespace(
                mol.get("molecule_chembl_id") or mol.get("chembl_id") or ""
            )
            if not chembl_id:
                continue
            detail_url = chembl_detail_url(base_url, chembl_id)
            detail_cache = request_cache_path(settings.cache_root, "chembl", detail_url)
            detail_record, detail_cache_hit = cached_get_json(
                detail_url,
                detail_cache,
                timeout=settings.timeout_seconds,
                retries=settings.max_retries,
                delay_seconds=settings.request_delay_seconds,
                source_name="ChEMBL",
                cache_enabled=settings.cache_responses,
                logger=logger,
            )
            request_meta.append(
                {
                    "url": detail_url,
                    "cache_hit": detail_cache_hit,
                    "status_code": detail_record.get("status_code", 0),
                    "ok": detail_record.get("ok", False),
                    "error": detail_record.get("error", ""),
                    "cache_path": str(detail_cache),
                    "term": term.to_dict(),
                    "detail": True,
                }
            )
            if not detail_record.get("ok"):
                # Fall back to the search result itself if detail is unavailable.
                detail_payload = mol
            else:
                detail_payload = detail_record.get("response_json") or mol

            hit = chembl_hit_from_detail(
                detail_payload,
                query_count=1,
                source_url=f"https://www.ebi.ac.uk/chembl/compound_report_card/{chembl_id}",
            )
            hit = score_hit(hit, terms, candidate)
            hits.append(hit)

    return hits, {"source": "ChEMBL", "requests": request_meta}


def group_hits_by_identifier(hits: List[SourceHit]) -> List[SourceHit]:
    best_by_id: Dict[Tuple[str, str], SourceHit] = {}
    for hit in hits:
        key = (hit.source_name, hit.identifier)
        existing = best_by_id.get(key)
        if existing is None or hit.match_score > existing.match_score:
            best_by_id[key] = hit
    return sorted(
        best_by_id.values(), key=lambda h: (-h.match_score, h.source_name, h.identifier)
    )


def boost_cross_source_agreement(hits: List[SourceHit]) -> Tuple[List[SourceHit], str]:
    # If PubChem and ChEMBL agree on InChIKey, add a modest boost.
    pubchem_keys = {
        h.inchi_key: h for h in hits if h.source_name == "PubChem" and h.inchi_key
    }
    chembl_keys = {
        h.inchi_key: h for h in hits if h.source_name == "ChEMBL" and h.inchi_key
    }
    common = sorted(set(pubchem_keys).intersection(set(chembl_keys)))
    if not common:
        return hits, ""

    common_key = common[0]
    for hit in hits:
        if hit.inchi_key == common_key:
            hit.match_score = min(0.99, hit.match_score + 0.06)
            hit.match_reason = (hit.match_reason + ";cross_source_inchikey").strip(";")
    return hits, common_key


def choose_best_hit(
    hits: List[SourceHit],
) -> Tuple[Optional[SourceHit], Optional[SourceHit], List[SourceHit]]:
    if not hits:
        return None, None, []
    ordered = sorted(hits, key=lambda h: (-h.match_score, h.source_name, h.identifier))
    best = ordered[0]
    second = ordered[1] if len(ordered) > 1 else None
    return best, second, ordered


def classify_enrichment_status(
    best: Optional[SourceHit],
    second: Optional[SourceHit],
    candidate: Dict[str, str],
    settings: Settings,
    review_reason: str,
) -> Tuple[str, str]:
    if best is None:
        return "unresolved", "no_hits"
    if best.match_score >= settings.high_confidence_threshold:
        if (
            second
            and abs(best.match_score - second.match_score) <= 0.03
            and best.identifier != second.identifier
        ):
            return "conflict", "top_hits_too_close"
        return "matched", ""
    if best.match_score >= settings.medium_confidence_threshold:
        if (
            second
            and abs(best.match_score - second.match_score) <= 0.03
            and best.identifier != second.identifier
        ):
            return "ambiguous", "top_hits_too_close"
        return "review", "below_high_confidence_threshold"
    if (
        second
        and abs(best.match_score - second.match_score) <= 0.03
        and best.identifier != second.identifier
    ):
        return "ambiguous", "low_confidence_tie"
    if normalize_whitespace(review_reason):
        return "review", "review_input_present"
    return "unresolved", "low_confidence"


def candidate_result_from_hit(
    candidate: Dict[str, str],
    best: Optional[SourceHit],
    second: Optional[SourceHit],
    status: str,
    reason: str,
    search_terms: List[SearchTerm],
    cache_key: str,
    cache_hit: bool,
    source_usage: Dict[str, int],
    run_id: str,
    settings: Settings,
    total_matches: int,
) -> Dict[str, Any]:
    retrieved_at = stable_timestamp(settings.batch_id)
    if best is None:
        return {
            "compound_candidate_id": candidate.get("compound_candidate_id", ""),
            "candidate_key": candidate.get("candidate_key", ""),
            "candidate_status": candidate.get("candidate_status", ""),
            "search_priority": candidate.get("search_priority", ""),
            "search_terms_json": json.dumps(
                [t.to_dict() for t in search_terms], ensure_ascii=False
            ),
            "pubchem_cid": "",
            "chembl_id": "",
            "inchi_key": "",
            "smiles": "",
            "molecular_formula": "",
            "molecular_weight": "",
            "tpsa": "",
            "logp": "",
            "hbond_donors": "",
            "hbond_acceptors": "",
            "rotatable_bonds": "",
            "qed_score": "",
            "np_likeness_score": "",
            "num_ro5_violations": "",
            "iupac_name": "",
            "preferred_name": "",
            "source_name": "",
            "source_url": "",
            "source_batch_id": run_id,
            "retrieved_at": retrieved_at,
            "enrichment_confidence": "0.0000",
            "enrichment_status": status,
            "match_strategy": "",
            "match_reason": reason,
            "match_rank": "",
            "match_count": str(total_matches),
            "cache_hit": str(cache_hit).lower(),
            "cache_key": cache_key,
            "review_reason": candidate.get("review_reason", ""),
        }

    enrichment_conf = f"{best.match_score:.4f}"
    chosen_name = (
        best.preferred_name
        or best.iupac_name
        or candidate.get("representative_name", "")
    )
    chosen_source_name = best.source_name
    chosen_source_url = best.source_url
    return {
        "compound_candidate_id": candidate.get("compound_candidate_id", ""),
        "candidate_key": candidate.get("candidate_key", ""),
        "candidate_status": candidate.get("candidate_status", ""),
        "search_priority": candidate.get("search_priority", ""),
        "search_terms_json": json.dumps(
            [t.to_dict() for t in search_terms], ensure_ascii=False
        ),
        "pubchem_cid": best.pubchem_cid,
        "chembl_id": best.chembl_id,
        "inchi_key": best.inchi_key,
        "smiles": best.smiles,
        "molecular_formula": best.molecular_formula,
        "molecular_weight": best.molecular_weight,
        "tpsa": best.tpsa,
        "logp": best.logp,
        "hbond_donors": best.hbond_donors,
        "hbond_acceptors": best.hbond_acceptors,
        "rotatable_bonds": best.rotatable_bonds,
        "qed_score": best.qed_score,
        "np_likeness_score": best.np_likeness_score,
        "num_ro5_violations": best.num_ro5_violations,
        "iupac_name": best.iupac_name,
        "preferred_name": chosen_name,
        "source_name": chosen_source_name,
        "source_url": chosen_source_url,
        "source_batch_id": run_id,
        "retrieved_at": retrieved_at,
        "enrichment_confidence": enrichment_conf,
        "enrichment_status": status,
        "match_strategy": best.matched_term_kind
        and f"{best.source_name.lower()}_{best.matched_term_kind}",
        "match_reason": ";".join([x for x in [best.match_reason, reason] if x]),
        "match_rank": "1",
        "match_count": str(total_matches),
        "cache_hit": str(cache_hit).lower(),
        "cache_key": cache_key,
        "review_reason": candidate.get("review_reason", ""),
    }


def build_member_map(
    candidate: Dict[str, str],
    members: List[Dict[str, str]],
    result: Dict[str, Any],
    status: str,
    confidence: float,
) -> List[Dict[str, Any]]:
    chosen_pubchem_cid = normalize_whitespace(result.get("pubchem_cid", ""))
    chosen_chembl_id = normalize_whitespace(result.get("chembl_id", ""))
    chosen_inchi_key = normalize_whitespace(result.get("inchi_key", ""))
    chosen_smiles = normalize_whitespace(result.get("smiles", ""))
    out: List[Dict[str, Any]] = []

    for member in members:
        out.append(
            {
                "compound_candidate_member_id": normalize_whitespace(
                    member.get("compound_candidate_member_id", "")
                ),
                "compound_candidate_id": normalize_whitespace(
                    candidate.get("compound_candidate_id", "")
                ),
                "source_row_hash": normalize_whitespace(
                    member.get("normalized_source_row_id")
                    or member.get("source_row_hash")
                    or member.get("raw_row_hash")
                    or member.get("source_compound_key")
                    or ""
                ),
                "source_compound_key": normalize_whitespace(
                    member.get("source_compound_key", "")
                ),
                "plant_id": normalize_whitespace(member.get("plant_id", "")),
                "canonical_plant_id": normalize_whitespace(
                    member.get("canonical_plant_id", "")
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
                "normalization_status": normalize_whitespace(
                    member.get("normalization_status", "")
                ),
                "review_reason": normalize_whitespace(member.get("review_reason", "")),
                "chosen_pubchem_cid": chosen_pubchem_cid,
                "chosen_chembl_id": chosen_chembl_id,
                "chosen_inchi_key": chosen_inchi_key,
                "chosen_smiles": chosen_smiles,
                "member_enrichment_status": status,
                "member_confidence": f"{confidence:.4f}",
            }
        )
    return out


def enrich_candidate(
    candidate: Dict[str, str],
    members: List[Dict[str, str]],
    review_row: Optional[Dict[str, str]],
    settings: Settings,
    logger: logging.Logger,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], bool]:
    terms = collect_search_terms(candidate, members, settings.max_terms_per_source)
    search_payload = candidate_search_payload(candidate, members, terms, settings)
    cache_key = candidate_cache_key(search_payload)
    cache_file = candidate_cache_path(settings.cache_root, cache_key)

    if settings.cache_responses and cache_file.exists():
        cached = safe_load_json(cache_file, logger)
        if cached is not None:
            result = cached.get("result", {})
            review_reason = cached.get("review_reason", "")
            status = cached.get("status", result.get("enrichment_status", "review"))
            confidence = float(
                cached.get("confidence", result.get("enrichment_confidence", 0.0))
                or 0.0
            )
            member_map = build_member_map(
                candidate, members, result, status, confidence
            )
            cache_index = {
                "cache_key": cache_key,
                "compound_candidate_id": candidate.get("compound_candidate_id", ""),
                "candidate_key": candidate.get("candidate_key", ""),
                "candidate_status": candidate.get("candidate_status", ""),
                "cache_hit": True,
                "request_count": int(cached.get("request_count", 0)),
                "request_cache_hits": int(cached.get("request_cache_hits", 0)),
                "request_cache_misses": int(cached.get("request_cache_misses", 0)),
                "selected_source_name": result.get("source_name", ""),
                "selected_identifier": result.get("pubchem_cid")
                or result.get("chembl_id")
                or "",
                "selected_inchi_key": result.get("inchi_key", ""),
                "selected_pubchem_cid": result.get("pubchem_cid", ""),
                "selected_chembl_id": result.get("chembl_id", ""),
                "enrichment_confidence": result.get("enrichment_confidence", "0.0000"),
                "cache_file": str(cache_file),
                "search_terms_json": json.dumps(
                    [t.to_dict() for t in terms], ensure_ascii=False
                ),
                "created_at": cached.get(
                    "created_at", stable_timestamp(settings.batch_id)
                ),
            }
            return result, member_map, cache_index, True

    cache_index_req_hits = 0
    cache_index_req_misses = 0
    source_usage = {
        "pubchem_requests": 0,
        "chembl_requests": 0,
        "pubchem_hits": 0,
        "chembl_hits": 0,
    }
    request_details: List[Dict[str, Any]] = []

    pubchem_hits, pubchem_meta = search_pubchem(
        candidate, terms, settings, logger, settings.cache_root
    )
    chembl_hits, chembl_meta = search_chembl(
        candidate, terms, settings, logger, settings.cache_root
    )

    request_details.extend(pubchem_meta.get("requests", []))
    request_details.extend(chembl_meta.get("requests", []))

    for req in request_details:
        if req.get("cache_hit"):
            cache_index_req_hits += 1
        else:
            cache_index_req_misses += 1

    source_usage["pubchem_requests"] = sum(
        1
        for r in request_details
        if "pubchem.ncbi.nlm.nih.gov" in str(r.get("url", ""))
    )
    source_usage["chembl_requests"] = sum(
        1 for r in request_details if "ebi.ac.uk/chembl" in str(r.get("url", ""))
    )
    source_usage["pubchem_hits"] = len(pubchem_hits)
    source_usage["chembl_hits"] = len(chembl_hits)

    all_hits = group_hits_by_identifier(pubchem_hits + chembl_hits)
    all_hits, cross_key = boost_cross_source_agreement(all_hits)
    best, second, ordered = choose_best_hit(all_hits)

    review_reason = normalize_whitespace(
        (review_row or {}).get("review_reason", "")
        or candidate.get("review_reason", "")
    )
    status, status_reason = classify_enrichment_status(
        best, second, candidate, settings, review_reason
    )

    # If we have a cross-source InChIKey agreement, choose the highest-scoring of that group.
    if cross_key and all_hits:
        cross_hits = [h for h in all_hits if h.inchi_key == cross_key]
        if cross_hits:
            cross_best = sorted(
                cross_hits, key=lambda h: (-h.match_score, h.source_name, h.identifier)
            )[0]
            if best is None or cross_best.match_score >= best.match_score:
                best = cross_best
                second = (
                    sorted(
                        [h for h in all_hits if h.identifier != cross_best.identifier],
                        key=lambda h: (-h.match_score, h.source_name, h.identifier),
                    )[0]
                    if len(all_hits) > 1
                    else None
                )

    total_matches = len(all_hits)

    # Build result row and preserve review handling.
    result = candidate_result_from_hit(
        candidate=candidate,
        best=best,
        second=second,
        status=status,
        reason=status_reason,
        search_terms=terms,
        cache_key=cache_key,
        cache_hit=False,
        source_usage=source_usage,
        run_id=stable_timestamp(settings.batch_id),
        settings=settings,
        total_matches=total_matches,
    )

    # Normalize result status if the selected hit is highly confident.
    if (
        best is not None
        and best.match_score >= settings.high_confidence_threshold
        and status == "review"
    ):
        result["enrichment_status"] = "matched"
    if best is not None and status in {"ambiguous", "conflict"}:
        result["review_reason"] = ";".join(
            [x for x in [review_reason, status_reason, best.match_reason] if x]
        )

    confidence = float(result.get("enrichment_confidence", "0.0") or 0.0)
    member_map = build_member_map(
        candidate, members, result, result["enrichment_status"], confidence
    )

    cache_payload = {
        "cache_key": cache_key,
        "candidate_id": candidate.get("compound_candidate_id", ""),
        "candidate_key": candidate.get("candidate_key", ""),
        "candidate_status": candidate.get("candidate_status", ""),
        "search_payload": search_payload,
        "search_terms": [t.to_dict() for t in terms],
        "request_details": request_details,
        "source_usage": source_usage,
        "ordered_hits": [
            {
                "source_name": h.source_name,
                "identifier": h.identifier,
                "source_url": h.source_url,
                "pubchem_cid": h.pubchem_cid,
                "chembl_id": h.chembl_id,
                "inchi_key": h.inchi_key,
                "smiles": h.smiles,
                "molecular_formula": h.molecular_formula,
                "molecular_weight": h.molecular_weight,
                "iupac_name": h.iupac_name,
                "preferred_name": h.preferred_name,
                "synonyms": list(h.synonyms),
                "match_score": h.match_score,
                "match_reason": h.match_reason,
                "matched_term": h.matched_term,
                "matched_term_kind": h.matched_term_kind,
            }
            for h in ordered
        ],
        "result": result,
        "status": result["enrichment_status"],
        "review_reason": result.get("review_reason", ""),
        "confidence": confidence,
        "request_count": len(request_details),
        "request_cache_hits": cache_index_req_hits,
        "request_cache_misses": cache_index_req_misses,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    cache_file.parent.mkdir(parents=True, exist_ok=True)
    with cache_file.open("w", encoding="utf-8") as f:
        json.dump(cache_payload, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")

    cache_index = {
        "cache_key": cache_key,
        "compound_candidate_id": candidate.get("compound_candidate_id", ""),
        "candidate_key": candidate.get("candidate_key", ""),
        "candidate_status": candidate.get("candidate_status", ""),
        "cache_hit": False,
        "request_count": len(request_details),
        "request_cache_hits": cache_index_req_hits,
        "request_cache_misses": cache_index_req_misses,
        "selected_source_name": result.get("source_name", ""),
        "selected_identifier": result.get("pubchem_cid")
        or result.get("chembl_id")
        or "",
        "selected_inchi_key": result.get("inchi_key", ""),
        "selected_pubchem_cid": result.get("pubchem_cid", ""),
        "selected_chembl_id": result.get("chembl_id", ""),
        "enrichment_confidence": result.get("enrichment_confidence", "0.0000"),
        "cache_file": str(cache_file),
        "search_terms_json": json.dumps(
            [t.to_dict() for t in terms], ensure_ascii=False
        ),
        "created_at": cache_payload["created_at"],
    }

    return result, member_map, cache_index, False


def enrich_candidate_task(
    idx: int,
    total: int,
    candidate: Dict[str, str],
    members: List[Dict[str, str]],
    review_row: Optional[Dict[str, str]],
    settings: Settings,
) -> Tuple[
    int, Dict[str, str], Dict[str, Any], List[Dict[str, Any]], Dict[str, Any], bool
]:
    logger = logging.getLogger("compounds.enrich")
    cid = normalize_whitespace(candidate.get("compound_candidate_id", ""))
    logger.info("Enriching candidate %d/%d: %s", idx, total, cid)
    try:
        result, member_map, cache_index, cache_hit = enrich_candidate(
            candidate, members, review_row, settings, logger
        )
        return idx, candidate, result, member_map, cache_index, cache_hit
    except Exception as exc:
        raise RuntimeError(f"Failed to enrich candidate {cid} ({idx}/{total})") from exc


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Enrich compound candidates from PubChem and ChEMBL."
    )
    parser.add_argument(
        "--settings",
        type=str,
        default=str(Path(__file__).resolve().parents[1] / "settings.yml"),
        help="Path to the compound ETL settings.yml file.",
    )
    args = parser.parse_args()

    settings = load_settings_for_enrich()
    run_id = make_run_id("compounds")

    log_path = configure_logging(settings.enrich_log_dir, run_id)
    logger = logging.getLogger("compounds.enrich")

    logger.info("Starting enrichment run_id=%s", run_id)
    logger.info("Settings path: %s", args.settings)
    logger.info("Candidate input: %s", settings.candidate_input_file)
    logger.info("Member input: %s", settings.member_input_file)
    logger.info("Review input: %s", settings.review_input_file)

    candidate_rows, members_by_candidate, review_by_candidate = load_candidate_inputs(
        settings
    )

    max_workers = min(6, max(1, len(candidate_rows)))
    logger.info("Using %d worker threads", max_workers)

    task_results: List[
        Optional[
            Tuple[
                Dict[str, str],
                Dict[str, Any],
                List[Dict[str, Any]],
                Dict[str, Any],
                bool,
            ]
        ]
    ] = [None] * len(candidate_rows)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = []
        for idx, candidate in enumerate(candidate_rows, start=1):
            cid = normalize_whitespace(candidate.get("compound_candidate_id", ""))
            members = members_by_candidate.get(cid, [])
            review_row = review_by_candidate.get(cid)
            futures.append(
                executor.submit(
                    enrich_candidate_task,
                    idx,
                    len(candidate_rows),
                    candidate,
                    members,
                    review_row,
                    settings,
                )
            )

        for future in as_completed(futures):
            idx, candidate, result, member_map, cache_index, cache_hit = future.result()
            task_results[idx - 1] = (
                candidate,
                result,
                member_map,
                cache_index,
                cache_hit,
            )
            logger.info(
                "Completed candidate %d/%d: %s (cache_hit=%s)",
                idx,
                len(candidate_rows),
                normalize_whitespace(candidate.get("compound_candidate_id", "")),
                cache_hit,
            )

    results: List[Dict[str, Any]] = []
    member_maps: List[Dict[str, Any]] = []
    review_rows: List[Dict[str, Any]] = []
    cache_index_rows: List[Dict[str, Any]] = []

    candidate_cache_hits = 0
    candidate_cache_misses = 0
    matched_count = 0
    review_count = 0
    ambiguous_count = 0
    unresolved_count = 0
    conflict_count = 0

    for idx, candidate in enumerate(candidate_rows, start=1):
        stored = task_results[idx - 1]
        if stored is None:
            raise RuntimeError(f"Missing enrichment result for candidate index {idx}")
        stored_candidate, result, member_map, cache_index, cache_hit = stored
        candidate = stored_candidate
        results.append(result)
        member_maps.extend(member_map)
        cache_index_rows.append(cache_index)

        if cache_hit:
            candidate_cache_hits += 1
        else:
            candidate_cache_misses += 1

        status = normalize_whitespace(result.get("enrichment_status", "")).lower()
        confidence = parse_float(result.get("enrichment_confidence", "")) or 0.0

        if status == "matched":
            matched_count += 1
        elif status == "review":
            review_count += 1
            review_rows.append(
                {
                    "compound_candidate_id": result.get("compound_candidate_id", ""),
                    "candidate_key": result.get("candidate_key", ""),
                    "candidate_status": result.get("candidate_status", ""),
                    "candidate_confidence": result.get("enrichment_confidence", ""),
                    "match_strategy": result.get("match_strategy", ""),
                    "match_reason": result.get("match_reason", ""),
                    "match_rank": result.get("match_rank", ""),
                    "match_count": result.get("match_count", ""),
                    "representative_name": candidate.get("representative_name", ""),
                    "representative_cas_id": candidate.get("representative_cas_id", ""),
                    "representative_formula": candidate.get(
                        "representative_formula", ""
                    ),
                    "representative_mw": candidate.get("representative_mw", ""),
                    "review_reason": result.get("review_reason", ""),
                    "source_name": result.get("source_name", ""),
                    "source_batch_id": result.get("source_batch_id", ""),
                    "retrieved_at": result.get("retrieved_at", ""),
                    "evidence_summary_json": json.dumps(
                        {
                            "member_count": candidate.get("member_count", ""),
                            "ready_member_count": candidate.get(
                                "ready_member_count", ""
                            ),
                            "review_member_count": candidate.get(
                                "review_member_count", ""
                            ),
                            "candidate_review_reason": candidate.get(
                                "review_reason", ""
                            ),
                            "enrichment_confidence": result.get(
                                "enrichment_confidence", ""
                            ),
                            "cache_hit": cache_hit,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        elif status == "ambiguous":
            ambiguous_count += 1
            review_rows.append(
                {
                    "compound_candidate_id": result.get("compound_candidate_id", ""),
                    "candidate_key": result.get("candidate_key", ""),
                    "candidate_status": result.get("candidate_status", ""),
                    "candidate_confidence": result.get("enrichment_confidence", ""),
                    "match_strategy": result.get("match_strategy", ""),
                    "match_reason": result.get("match_reason", ""),
                    "match_rank": result.get("match_rank", ""),
                    "match_count": result.get("match_count", ""),
                    "representative_name": candidate.get("representative_name", ""),
                    "representative_cas_id": candidate.get("representative_cas_id", ""),
                    "representative_formula": candidate.get(
                        "representative_formula", ""
                    ),
                    "representative_mw": candidate.get("representative_mw", ""),
                    "review_reason": result.get("review_reason", ""),
                    "source_name": result.get("source_name", ""),
                    "source_batch_id": result.get("source_batch_id", ""),
                    "retrieved_at": result.get("retrieved_at", ""),
                    "evidence_summary_json": json.dumps(
                        {
                            "member_count": candidate.get("member_count", ""),
                            "candidate_review_reason": candidate.get(
                                "review_reason", ""
                            ),
                            "enrichment_confidence": result.get(
                                "enrichment_confidence", ""
                            ),
                            "cache_hit": cache_hit,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        elif status == "conflict":
            conflict_count += 1
            review_rows.append(
                {
                    "compound_candidate_id": result.get("compound_candidate_id", ""),
                    "candidate_key": result.get("candidate_key", ""),
                    "candidate_status": result.get("candidate_status", ""),
                    "candidate_confidence": result.get("enrichment_confidence", ""),
                    "match_strategy": result.get("match_strategy", ""),
                    "match_reason": result.get("match_reason", ""),
                    "match_rank": result.get("match_rank", ""),
                    "match_count": result.get("match_count", ""),
                    "representative_name": candidate.get("representative_name", ""),
                    "representative_cas_id": candidate.get("representative_cas_id", ""),
                    "representative_formula": candidate.get(
                        "representative_formula", ""
                    ),
                    "representative_mw": candidate.get("representative_mw", ""),
                    "review_reason": result.get("review_reason", ""),
                    "source_name": result.get("source_name", ""),
                    "source_batch_id": result.get("source_batch_id", ""),
                    "retrieved_at": result.get("retrieved_at", ""),
                    "evidence_summary_json": json.dumps(
                        {
                            "member_count": candidate.get("member_count", ""),
                            "candidate_review_reason": candidate.get(
                                "review_reason", ""
                            ),
                            "enrichment_confidence": result.get(
                                "enrichment_confidence", ""
                            ),
                            "cache_hit": cache_hit,
                        },
                        ensure_ascii=False,
                    ),
                }
            )
        else:
            unresolved_count += 1
            if confidence < settings.medium_confidence_threshold:
                review_rows.append(
                    {
                        "compound_candidate_id": result.get(
                            "compound_candidate_id", ""
                        ),
                        "candidate_key": result.get("candidate_key", ""),
                        "candidate_status": result.get("candidate_status", ""),
                        "candidate_confidence": result.get("enrichment_confidence", ""),
                        "match_strategy": result.get("match_strategy", ""),
                        "match_reason": result.get("match_reason", ""),
                        "match_rank": result.get("match_rank", ""),
                        "match_count": result.get("match_count", ""),
                        "representative_name": candidate.get("representative_name", ""),
                        "representative_cas_id": candidate.get(
                            "representative_cas_id", ""
                        ),
                        "representative_formula": candidate.get(
                            "representative_formula", ""
                        ),
                        "representative_mw": candidate.get("representative_mw", ""),
                        "review_reason": result.get("review_reason", ""),
                        "source_name": result.get("source_name", ""),
                        "source_batch_id": result.get("source_batch_id", ""),
                        "retrieved_at": result.get("retrieved_at", ""),
                        "evidence_summary_json": json.dumps(
                            {
                                "member_count": candidate.get("member_count", ""),
                                "candidate_review_reason": candidate.get(
                                    "review_reason", ""
                                ),
                                "enrichment_confidence": result.get(
                                    "enrichment_confidence", ""
                                ),
                                "cache_hit": cache_hit,
                            },
                            ensure_ascii=False,
                        ),
                    }
                )

    out_results = settings.enrich_out_dir / "compound_enrichment_results.csv"

    out_cache_index = settings.enrich_out_dir / "compound_enrichment_cache.csv"
    out_member_map = settings.enrich_out_dir / "compound_enrichment_member_map.csv"
    out_review = settings.enrich_out_dir / "compound_enrichment_review.csv"
    out_summary = settings.enrich_out_dir / "enrich_summary.json"

    _write_csv_local(out_results, results, RESULT_COLUMNS)
    _write_csv_local(out_cache_index, cache_index_rows, CACHE_INDEX_COLUMNS)
    _write_csv_local(out_member_map, member_maps, MEMBER_MAP_COLUMNS)
    _write_csv_local(out_review, review_rows, REVIEW_COLUMNS)

    summary = {
        "module": "compounds",
        "step": "04_enrich",
        "run_id": run_id,
        "settings_file": str(args.settings),
        "candidate_input_file": str(settings.candidate_input_file),
        "member_input_file": str(settings.member_input_file),
        "review_input_file": str(settings.review_input_file),
        "output_results_file": str(out_results),
        "output_cache_index_file": str(out_cache_index),
        "output_member_map_file": str(out_member_map),
        "output_review_file": str(out_review),
        "log_file": str(log_path),
        "cache_root": str(settings.cache_root),
        "candidates_processed": len(candidate_rows),
        "candidate_cache_hits": candidate_cache_hits,
        "candidate_cache_misses": candidate_cache_misses,
        "matched_rows": matched_count,
        "review_rows": review_count,
        "ambiguous_rows": ambiguous_count,
        "unresolved_rows": unresolved_count,
        "conflict_rows": conflict_count,
        "member_map_rows": len(member_maps),
        "source_usage": {
            "pubchem_requests": sum(
                row.get("request_count", 0)
                for row in cache_index_rows
                if "pubchem" in json.dumps(row).lower()
            ),
            "chembl_requests": sum(
                row.get("request_count", 0)
                for row in cache_index_rows
                if "chembl" in json.dumps(row).lower()
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
    if settings.write_summary_json:
        _write_json_local(out_summary, summary)
        summary["summary_file"] = str(out_summary)

    logger.info("Candidates processed: %d", len(candidate_rows))
    logger.info("Cache hits: %d", candidate_cache_hits)
    logger.info("Matched: %d", matched_count)
    logger.info("Review: %d", review_count)
    logger.info("Ambiguous: %d", ambiguous_count)
    logger.info("Unresolved: %d", unresolved_count)
    logger.info("Conflict: %d", conflict_count)
    logger.info("Results: %s", out_results)
    logger.info("Cache index: %s", out_cache_index)
    logger.info("Member map: %s", out_member_map)
    logger.info("Review: %s", out_review)
    if settings.write_summary_json:
        logger.info("Summary: %s", out_summary)
    logger.info("Completed successfully")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
