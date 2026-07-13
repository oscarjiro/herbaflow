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
import argparse
import csv
import hashlib
import json
import logging
import math
import os
import random
import re
import socket
import threading
import time
from collections import defaultdict, deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from http.client import IncompleteRead, RemoteDisconnected
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from shared.identity import formula_matches
from shared.utils import ETL_ROOT, ensure_dir, make_run_id, normalize_whitespace
from shared.utils import load_settings as shared_load_settings

# Sibling module (04_enrich/): inline ADME / property computation that replaced
# the retired patch_missing_smiles.py / patch_missing_lipinski.py post-passes.
sys.path.insert(0, str(Path(__file__).resolve().parent))  # 04_enrich/
from properties import (  # noqa: E402
    chembl_detail_by_inchikey,
    check_pains,
    np_likeness,
    rdkit_descriptors,
)

# Bump when the identity-acceptance logic changes so stale per-candidate caches
# (out/cache/candidates/) are recomputed while the raw HTTP cache stays valid.
ENRICH_LOGIC_VERSION = "2026-07-13-knapsack-anchor"

# KNApSAcK source structures, keyed by ``c_id`` -> (inchikey, smiles, formula).
# Populated once in main() from the scraper output. Empty until the source-first
# re-scrape writes the ``knapsack_*`` columns; while empty the anchor never fires
# and every candidate falls through to the external PubChem/ChEMBL identity search.
structure_by_cid: Dict[str, Tuple[str, str, str]] = {}

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
    "evidence_type",
    "match_reason",
    "match_rank",
    "match_count",
    "cache_hit",
    "cache_key",
    "review_reason",
    "lipinski_source",
    "is_pains_positive",
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
    max_requests_per_second: float
    max_requests_per_minute: int
    max_requests_per_candidate: int
    enrich_limit: int


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


class RateLimiter:
    """Process-wide, thread-safe limiter honoring both a per-second and a
    per-minute cap. Used to keep live API traffic within PubChem's published
    PUG-REST limits (<=5 requests/second, <=400 requests/minute per IP) across
    the enrichment thread pool. Cache hits do not consume the budget.
    """

    def __init__(self, max_per_second: float, max_per_minute: int) -> None:
        self._min_interval = 1.0 / max_per_second if max_per_second > 0 else 0.0
        self._max_per_minute = max(0, int(max_per_minute))
        self._lock = threading.Lock()
        self._last_ts = 0.0
        self._window: deque[float] = deque()

    def acquire(self) -> None:
        while True:
            with self._lock:
                now = time.monotonic()
                # Per-minute window.
                if self._max_per_minute > 0:
                    while self._window and now - self._window[0] >= 60.0:
                        self._window.popleft()
                    if len(self._window) >= self._max_per_minute:
                        sleep_for = 60.0 - (now - self._window[0])
                        wait = max(0.0, sleep_for)
                    else:
                        wait = 0.0
                else:
                    wait = 0.0
                # Per-second spacing (only if the minute window is not blocking).
                if wait <= 0.0:
                    gap = self._min_interval - (now - self._last_ts)
                    if gap > 0:
                        wait = gap
                if wait <= 0.0:
                    self._last_ts = now
                    if self._max_per_minute > 0:
                        self._window.append(now)
                    return
            time.sleep(wait)


_RATE_LIMITERS: dict[str, RateLimiter] = {}
_RATE_LIMITER_GUARD = threading.Lock()


def get_rate_limiter(
    source_name: str, max_per_second: float, max_per_minute: int
) -> RateLimiter:
    with _RATE_LIMITER_GUARD:
        limiter = _RATE_LIMITERS.get(source_name)
        if limiter is None:
            limiter = RateLimiter(max_per_second, max_per_minute)
            _RATE_LIMITERS[source_name] = limiter
        return limiter


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
        # PubChem PUG-REST usage policy: no more than 5 requests/second and
        # 400 requests/minute per IP. ChEMBL is more permissive; the shared cap
        # keeps us safe for both. Configurable but defaulted to the PubChem limit.
        max_requests_per_second=float(pubchem_cfg.get("max_requests_per_second", 5.0)),
        max_requests_per_minute=int(pubchem_cfg.get("max_requests_per_minute", 400)),
        # Per-candidate request cap across PubChem+ChEMBL. Stops a non-corroborating
        # candidate from exhausting every source/term before evaluate_identity
        # rejects it anyway. Corroborated candidates early-exit well under this.
        max_requests_per_candidate=int(
            enrichment_cfg.get("max_requests_per_candidate", 8)
        ),
        # Smoke/sample cap: process only the first N candidates when > 0. Set via
        # the ENRICH_LIMIT env var or the --limit CLI flag (flag wins).
        enrich_limit=int(os.environ.get("ENRICH_LIMIT", "0") or "0"),
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


def load_structure_by_cid(path: Path) -> Dict[str, Tuple[str, str, str]]:
    """Map KNApSAcK ``c_id`` -> (inchikey, smiles, formula) from the scraper output.

    Reads the three ``knapsack_*`` structure columns DEFENSIVELY: they are written
    only by the source-first re-scrape, so a CSV that predates it yields an empty
    map (never a KeyError). Only rows with a non-empty ``knapsack_inchikey`` are
    kept, since a structure with no InChIKey cannot anchor identity. Structure
    fields are stored AS PUBLISHED (no normalization) so the accepted identity is
    exactly what KNApSAcK ships.
    """
    mapping: Dict[str, Tuple[str, str, str]] = {}
    if not path.exists():
        return mapping
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            cid = normalize_whitespace(row.get("c_id", ""))
            inchikey = normalize_whitespace(row.get("knapsack_inchikey", ""))
            if not cid or not inchikey:
                continue
            smiles = normalize_whitespace(row.get("knapsack_smiles", ""))
            formula = normalize_whitespace(row.get("knapsack_formula", ""))
            mapping[cid] = (inchikey, smiles, formula)
    return mapping


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
        "logic_version": ENRICH_LOGIC_VERSION,
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


def _retry_after_seconds(exc: HTTPError, fallback: float) -> float:
    """Honor a Retry-After response header (seconds form) when the server sends
    one on a 429/503, bounded so a hostile header cannot stall the run."""
    try:
        header = exc.headers.get("Retry-After") if exc.headers else None
    except Exception:
        header = None
    if header:
        try:
            return max(0.0, min(60.0, float(str(header).strip())))
        except ValueError:
            return fallback
    return fallback


def cached_get_json(
    url: str,
    cache_path: Path,
    timeout: int,
    retries: int,
    delay_seconds: float,
    source_name: str,
    cache_enabled: bool,
    logger: logging.Logger,
    rate_per_second: float = 5.0,
    rate_per_minute: int = 400,
) -> Tuple[Dict[str, Any], bool]:
    if cache_enabled and cache_path.exists():
        cached = safe_load_json(cache_path, logger)
        if cached is not None:
            return cached, True

    cache_path.parent.mkdir(parents=True, exist_ok=True)
    limiter = get_rate_limiter(source_name, rate_per_second, rate_per_minute)
    last_error: Optional[str] = None
    for attempt in range(retries + 1):
        if attempt > 0:
            sleep_for = delay_seconds * (2 ** (attempt - 1))
            time.sleep(sleep_for)
        # Stay within the source's published request-rate budget for every live
        # request (cache hits above never reach here).
        limiter.acquire()
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
                if exc.code in {429, 503}:
                    # Server is throttling us: wait out Retry-After (or a backoff)
                    # before the next attempt, on top of the exponential delay.
                    time.sleep(_retry_after_seconds(exc, delay_seconds * (2**attempt)))
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
            IncompleteRead,
            TimeoutError,
            socket.timeout,
            ConnectionError,
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
    # PubChem PUG-REST renamed its SMILES properties in 2025:
    # CanonicalSMILES -> ConnectivitySMILES, IsomericSMILES -> SMILES. Request the
    # current names; the parser still accepts the legacy keys for cached responses.
    props = "IUPACName,ConnectivitySMILES,SMILES,InChIKey,MolecularFormula,MolecularWeight,Title"
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
        # PubChem renamed CanonicalSMILES -> ConnectivitySMILES and
        # IsomericSMILES -> SMILES (2025). Read the current keys first, falling
        # back to the legacy names so pre-rename cached responses still resolve.
        smiles=normalize_whitespace(
            prop.get("ConnectivitySMILES")
            or prop.get("SMILES")
            or prop.get("CanonicalSMILES")
            or prop.get("IsomericSMILES")
            or ""
        ),
        molecular_formula=normalize_whitespace(prop.get("MolecularFormula") or ""),
        molecular_weight=normalize_whitespace(prop.get("MolecularWeight") or ""),
        iupac_name=normalize_whitespace(prop.get("IUPACName") or ""),
        preferred_name=normalize_whitespace(
            prop.get("Title")
            or prop.get("IUPACName")
            or prop.get("ConnectivitySMILES")
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


class RequestBudget:
    """Per-candidate cap on PubChem+ChEMBL requests issued while searching for a
    corroborated identity.

    A candidate that never corroborates would otherwise exhaust every CAS/name
    term across both sources (14-26 requests); once the budget is spent we stop
    fishing and let ``evaluate_identity`` reject it on the hits gathered so far.
    That is the same raw-identity fallback it reaches anyway, just sooner.
    Corroborated candidates early-exit (via ``stop_check``) well under the budget
    (~3-4 requests), so their accepted structure is never affected. One candidate
    is processed by a single worker thread, so no locking is needed.
    """

    def __init__(self, max_requests: int) -> None:
        self.max_requests = max(0, int(max_requests))
        self.used = 0

    def charge(self) -> None:
        self.used += 1

    def exhausted(self) -> bool:
        return self.max_requests > 0 and self.used >= self.max_requests


def search_pubchem(
    candidate: Dict[str, str],
    terms: List[SearchTerm],
    settings: Settings,
    logger: logging.Logger,
    request_cache_dir: Path,
    stop_check: Optional[Callable[[List[SourceHit]], bool]] = None,
    budget: Optional["RequestBudget"] = None,
) -> Tuple[List[SourceHit], Dict[str, Any]]:
    base_url = settings.pubchem_cfg.get(
        "base_url", "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    )
    hits: List[SourceHit] = []
    request_meta: List[Dict[str, Any]] = []
    term_count = 0

    # Only CAS and name terms are searched (reliable-first: collect_search_terms
    # already orders CAS before name). Formula and molecular-weight searches are
    # never issued: under the corroboration gate an identity can be accepted only
    # via a CAS / name / cross-source signal WITH formula agreement, so a
    # formula-search or MW hit can never be accepted. Fetching them is pure wasted
    # latency. The full ``terms`` list is still used for scoring, so hit scores and
    # ordering are unchanged.
    for term in terms:
        if term.kind not in ("cas", "name"):
            continue
        if term_count >= settings.max_terms_per_source:
            break
        # Stop fishing once the per-candidate request budget is spent (a
        # non-corroborating candidate would otherwise exhaust every term).
        if budget is not None and budget.exhausted():
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
        if budget is not None:
            budget.charge()
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
            if budget is not None and budget.exhausted():
                break
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
                rate_per_second=settings.max_requests_per_second,
                rate_per_minute=settings.max_requests_per_minute,
            )
            if budget is not None:
                budget.charge()
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
                rate_per_second=settings.max_requests_per_second,
                rate_per_minute=settings.max_requests_per_minute,
            )
            if budget is not None:
                budget.charge()
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

        # Early-exit: once a formula-corroborated CAS/name hit is in hand, stop
        # issuing further term searches for this candidate (the accept decision is
        # already settled; remaining fetches cannot change it).
        if stop_check is not None and stop_check(hits):
            break

    return hits, {"source": "PubChem", "requests": request_meta}


def search_chembl(
    candidate: Dict[str, str],
    terms: List[SearchTerm],
    settings: Settings,
    logger: logging.Logger,
    request_cache_dir: Path,
    stop_check: Optional[Callable[[List[SourceHit]], bool]] = None,
    budget: Optional["RequestBudget"] = None,
) -> Tuple[List[SourceHit], Dict[str, Any]]:
    base_url = settings.chembl_cfg.get(
        "base_url", "https://www.ebi.ac.uk/chembl/api/data"
    )
    hits: List[SourceHit] = []
    request_meta: List[Dict[str, Any]] = []
    term_count = 0

    # Only CAS and name terms are searched (see search_pubchem for the rationale):
    # a formula-search or MW hit can never clear the corroboration gate.
    for term in terms:
        if term.kind not in ("cas", "name"):
            continue
        if term_count >= settings.max_terms_per_source:
            break
        # Budget is shared with the PubChem pass, so ChEMBL only runs on the
        # remainder left after PubChem failed to corroborate.
        if budget is not None and budget.exhausted():
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
        if budget is not None:
            budget.charge()
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
            if budget is not None and budget.exhausted():
                break
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
                rate_per_second=settings.max_requests_per_second,
                rate_per_minute=settings.max_requests_per_minute,
            )
            if budget is not None:
                budget.charge()
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

        # Early-exit once a formula-corroborated CAS/name hit is in hand.
        if stop_check is not None and stop_check(hits):
            break

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


# --- Identity acceptance: gate on CORROBORATION, not on the guess's output ---
#
# A source hit is accepted as authoritative structural identity ONLY when the
# evidence for it is corroborated. The single decisive new check is molecular
# formula agreement: a correct resolution preserves the raw source formula, so
# the hit's formula must equal the candidate's raw formula (Hill-normalized).
#
#   ACCEPT (reliable, structure emitted):
#     - CAS term matches the hit AND the formula agrees          -> cas_formula_confirmed
#     - PubChem+ChEMBL agree on InChIKey AND the formula agrees  -> cross_source_confirmed
#     - a strong NAME match AND the formula agrees               -> name_formula_confirmed
#   REJECT (structure dropped; falls back to raw name_formula/name/cas identity):
#     - name-only (formula unavailable or disagrees)
#     - formula-only (isomer-blind, no CAS/name/structure corroboration)
#     - molecular-weight-only
#     - an ambiguous tie between distinct structures with no corroboration
#     - a CAS/name match whose formula disagrees (wrong molecule)
#
# KNApSAcK ships no InChIKey, so the raw-InChIKey path is not reachable here; it
# is covered by the cross-source structural agreement check instead.

_CAS_SIGNAL_MIN = 0.88  # any real CAS synonym/name match
_NAME_SIGNAL_MIN = 0.88  # exact/iupac/synonym name match; excludes fuzzy 0.78
_TIE_WINDOW = 0.03
_CONF_STRUCTURAL = 0.97  # cas+formula or cross-source+formula
_CONF_NAME_FORMULA = 0.90  # name+formula
_CONF_REJECTED = 0.30  # honest low: no corroborated structural identity


@dataclass(frozen=True)
class IdentityDecision:
    accepted: bool
    hit: Optional[SourceHit]
    strategy: str
    evidence_type: str
    confidence: float
    status: str
    reason: str
    rank: str
    count: str


def _hit_signals(
    candidate: Dict[str, str], terms: List[SearchTerm], hit: SourceHit
) -> Tuple[bool, bool, bool]:
    """Return (cas_signal, name_signal, formula_agrees) for a hit vs the raw
    candidate. cas/name signals require a strong term match; formula_agrees
    requires Hill-normalized equality of the raw and resolved formulas."""
    formula_agrees = formula_matches(
        candidate.get("representative_formula", ""), hit.molecular_formula
    )
    cas_signal = False
    name_signal = False
    for term in terms:
        if term.kind == "cas":
            score, _ = build_term_match_score(term, hit)
            if score >= _CAS_SIGNAL_MIN:
                cas_signal = True
        elif term.kind == "name":
            score, _ = build_term_match_score(term, hit)
            if score >= _NAME_SIGNAL_MIN:
                name_signal = True
    return cas_signal, name_signal, formula_agrees


def _hit_accept_ready(
    candidate: Dict[str, str], terms: List[SearchTerm], hit: SourceHit
) -> bool:
    """True when this single hit already satisfies an accept path that needs only
    one source: a strong CAS or name signal WITH molecular-formula agreement.

    This is exactly the ``cas_signal``/``name_signal`` accept branches of
    ``evaluate_identity`` (the cross-source branch needs both sources and is
    intentionally excluded here). It lets the fetch loop stop the moment a
    formula-corroborated hit is in hand, without re-deriving accept behavior."""
    cas_signal, name_signal, formula_agrees = _hit_signals(candidate, terms, hit)
    return formula_agrees and (cas_signal or name_signal)


def evaluate_identity(
    candidate: Dict[str, str],
    terms: List[SearchTerm],
    ordered_hits: List[SourceHit],
    cross_key: str,
) -> IdentityDecision:
    if not ordered_hits:
        return IdentityDecision(
            accepted=False,
            hit=None,
            strategy="",
            evidence_type="none",
            confidence=0.0,
            status="unresolved",
            reason="no_hits",
            rank="",
            count="0",
        )

    # Count distinct candidate structures (InChIKey, else source+identifier) so a
    # genuine multi-structure tie can be detected and rejected.
    seen_structs: set[str] = set()
    for hit in ordered_hits:
        seen_structs.add(hit.inchi_key or f"{hit.source_name}:{hit.identifier}")
    distinct_count = len(seen_structs)

    # Try the reliable path first: find every corroborated hit, keep the best.
    corroborated: List[Tuple[SourceHit, str, str, float]] = []
    for hit in ordered_hits:
        cas_signal, name_signal, formula_agrees = _hit_signals(candidate, terms, hit)
        if not formula_agrees:
            continue
        if cas_signal:
            corroborated.append(
                (hit, "cas_formula_confirmed", "cas+formula", _CONF_STRUCTURAL)
            )
        elif hit.inchi_key and cross_key and hit.inchi_key == cross_key:
            corroborated.append(
                (
                    hit,
                    "cross_source_confirmed",
                    "cross_source+formula",
                    _CONF_STRUCTURAL,
                )
            )
        elif name_signal:
            corroborated.append(
                (hit, "name_formula_confirmed", "name+formula", _CONF_NAME_FORMULA)
            )

    if corroborated:
        hit, strategy, evidence_type, confidence = max(
            corroborated, key=lambda item: item[0].match_score
        )
        rank = str(ordered_hits.index(hit) + 1)
        reason = ";".join(
            [x for x in [hit.match_reason, f"corroborated_{evidence_type}"] if x]
        )
        return IdentityDecision(
            accepted=True,
            hit=hit,
            strategy=strategy,
            evidence_type=evidence_type,
            confidence=confidence,
            status="matched",
            reason=reason,
            rank=rank,
            count=str(distinct_count),
        )

    # No corroborated identity -> reject and record WHY (honest provenance).
    best = ordered_hits[0]
    second = ordered_hits[1] if len(ordered_hits) > 1 else None
    cas_signal, name_signal, formula_agrees = _hit_signals(candidate, terms, best)
    tie = (
        second is not None
        and abs(best.match_score - second.match_score) <= _TIE_WINDOW
        and (best.inchi_key or best.identifier)
        != (second.inchi_key or second.identifier)
    )

    if tie and distinct_count >= 2:
        strategy, evidence_type = "rejected_ambiguous_tie", "ambiguous"
    elif formula_agrees and not (cas_signal or name_signal):
        strategy, evidence_type = "rejected_formula_only", "formula_only"
    elif name_signal and not formula_agrees:
        strategy, evidence_type = "rejected_name_only", "name_only"
    elif cas_signal and not formula_agrees:
        strategy, evidence_type = "rejected_formula_mismatch", "cas_no_formula_confirm"
    elif best.matched_term_kind == "mw":
        strategy, evidence_type = "rejected_mw", "mw_only"
    else:
        strategy, evidence_type = "rejected_uncorroborated", "weak"

    reason = (
        f"{strategy};best={best.source_name}:{best.identifier};"
        f"score={best.match_score:.2f}"
    )
    return IdentityDecision(
        accepted=False,
        hit=None,
        strategy=strategy,
        evidence_type=evidence_type,
        confidence=_CONF_REJECTED,
        status="review",
        reason=reason,
        rank="",
        count=str(distinct_count),
    )


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
            "evidence_type": "none",
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
        "evidence_type": "",
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


def _read_http_cache(
    cache_root: Path, source: str, url: str
) -> Optional[Dict[str, Any]]:
    """Return a cached HTTP record for ``url`` if present, else None. Never
    fetches — cache-only introspection so the KNApSAcK anchor's safety probe stays
    network-free."""
    path = request_cache_path(cache_root, source, url)
    if not path.exists():
        return None
    record = safe_load_json(path)
    return record if isinstance(record, dict) else None


def _cached_external_inchikeys(
    candidate: Dict[str, str],
    terms: List[SearchTerm],
    settings: Settings,
    logger: logging.Logger,
) -> set[str]:
    """Upper-cased InChIKeys already present in the raw HTTP cache for this
    candidate's PubChem/ChEMBL search terms.

    Cache-only: it reconstructs the same request URLs the search would use and
    reads only existing cache files, never issuing a request (so the anchor path
    performs no new fetch). Empty when nothing relevant is cached."""
    keys: set[str] = set()
    base_pc = settings.pubchem_cfg.get(
        "base_url", "https://pubchem.ncbi.nlm.nih.gov/rest/pug"
    )
    base_ch = settings.chembl_cfg.get(
        "base_url", "https://www.ebi.ac.uk/chembl/api/data"
    )
    term_count = 0
    for term in terms:
        if term.kind not in ("cas", "name"):
            continue
        if term_count >= settings.max_terms_per_source:
            break
        term_count += 1
        try:
            rec = _read_http_cache(
                settings.cache_root,
                "pubchem",
                pubchem_search_url(base_pc, term.text, term.kind),
            )
            if rec and rec.get("ok"):
                cids = extract_pubchem_cids(rec.get("response_json") or {})
                for cid in cids[: settings.max_pubchem_cids]:
                    drec = _read_http_cache(
                        settings.cache_root,
                        "pubchem",
                        pubchem_properties_url(base_pc, cid),
                    )
                    if drec and drec.get("ok"):
                        for prop in extract_pubchem_properties(
                            drec.get("response_json") or {}
                        ):
                            ik = normalize_whitespace(prop.get("InChIKey") or "")
                            if ik:
                                keys.add(ik.upper())
            crec = _read_http_cache(
                settings.cache_root, "chembl", chembl_search_url(base_ch, term.text)
            )
            if crec and crec.get("ok"):
                for mol in extract_chembl_molecules(crec.get("response_json") or {}):
                    hit = chembl_hit_from_detail(mol, query_count=0, source_url="")
                    ik = normalize_whitespace(hit.inchi_key)
                    if ik:
                        keys.add(ik.upper())
        except Exception as exc:  # noqa: BLE001 - probe must never break an accept
            logger.debug("cached inchikey probe skipped for %r: %s", term.text, exc)
    return keys


def knapsack_structure_for_candidate(
    candidate: Dict[str, str], members: List[Dict[str, str]]
) -> Optional[Tuple[str, str, str, str]]:
    """Return (c_id, inchikey, smiles, formula) of the first candidate member
    whose KNApSAcK-published structure formula corroborates the raw representative
    formula (charge/desalt-aware via ``formula_matches``), or None when no member
    has a corroborating source structure."""
    raw_formula = candidate.get("representative_formula", "")
    for member in members:
        cid = normalize_whitespace(member.get("c_id", ""))
        if not cid:
            continue
        struct = structure_by_cid.get(cid)
        if not struct:
            continue
        inchikey, smiles, formula = struct
        if not normalize_whitespace(inchikey):
            continue
        if formula_matches(raw_formula, formula):
            return cid, inchikey, smiles, formula
    return None


def build_knapsack_anchor_result(
    candidate: Dict[str, str],
    members: List[Dict[str, str]],
    terms: List[SearchTerm],
    search_payload: Dict[str, Any],
    cache_key: str,
    cache_file: Path,
    matched_cid: str,
    inchi_key: str,
    smiles: str,
    molecular_formula: str,
    review_row: Optional[Dict[str, str]],
    settings: Settings,
    logger: logging.Logger,
) -> Tuple[Dict[str, Any], List[Dict[str, Any]], Dict[str, Any]]:
    """Assemble the accepted enrichment result for a KNApSAcK-source-confirmed
    identity: structure fields AS PUBLISHED, ADME computed inline (RDKit for the
    Lipinski descriptors + molecular weight, ChEMBL by InChIKey for QED / RO5, NP
    from ChEMBL else the RDKit NP scorer, PAINS from RDKit), honest provenance, and
    a written per-candidate cache. No external identity search is performed, and
    KNApSAcK's structure is never overridden."""
    run_id = stable_timestamp(settings.batch_id)
    inchi_key = normalize_whitespace(inchi_key)
    smiles = normalize_whitespace(smiles)
    molecular_formula = normalize_whitespace(molecular_formula)

    descriptors = rdkit_descriptors(smiles) if smiles else None
    descriptors = descriptors or {}
    chembl_cache_dir = settings.cache_root / "http" / "chembl"
    chembl_props = (
        chembl_detail_by_inchikey(inchi_key, chembl_cache_dir) if inchi_key else {}
    )
    np_score = chembl_props.get("np_likeness_score") or (
        np_likeness(smiles) if smiles else ""
    )
    is_pains = check_pains(smiles) if smiles else False
    lipinski_source = "rdkit_computed" if descriptors else ""

    review_reason = normalize_whitespace(
        (review_row or {}).get("review_reason", "")
        or candidate.get("review_reason", "")
    )

    reasons = [f"knapsack_source_confirmed;c_id={matched_cid};formula_confirmed"]
    external_keys = _cached_external_inchikeys(candidate, terms, settings, logger)
    if external_keys and inchi_key.upper() not in external_keys:
        reasons.append("knapsack_vs_external_disagreement")
    if review_reason:
        reasons.append(review_reason)
    match_reason = ";".join([r for r in reasons if r])

    result: Dict[str, Any] = {
        "compound_candidate_id": candidate.get("compound_candidate_id", ""),
        "candidate_key": candidate.get("candidate_key", ""),
        "candidate_status": candidate.get("candidate_status", ""),
        "search_priority": candidate.get("search_priority", ""),
        "search_terms_json": json.dumps(
            [t.to_dict() for t in terms], ensure_ascii=False
        ),
        "pubchem_cid": "",
        "chembl_id": "",
        "inchi_key": inchi_key,
        "smiles": smiles,
        "molecular_formula": molecular_formula,
        "molecular_weight": descriptors.get("molecular_weight", ""),
        "tpsa": descriptors.get("tpsa", ""),
        "logp": descriptors.get("logp", ""),
        "hbond_donors": descriptors.get("hbond_donors", ""),
        "hbond_acceptors": descriptors.get("hbond_acceptors", ""),
        "rotatable_bonds": descriptors.get("rotatable_bonds", ""),
        "qed_score": chembl_props.get("qed_score", ""),
        "np_likeness_score": np_score,
        "num_ro5_violations": chembl_props.get("num_ro5_violations", ""),
        "iupac_name": "",
        "preferred_name": candidate.get("representative_name", ""),
        "source_name": settings.source_name,
        "source_url": candidate.get("source_url", "") or settings.source_url,
        "source_batch_id": run_id,
        "retrieved_at": run_id,
        "enrichment_confidence": "0.9700",
        "enrichment_status": "matched",
        "match_strategy": "knapsack_source_confirmed",
        "evidence_type": "knapsack+formula",
        "match_reason": match_reason,
        "match_rank": "1",
        "match_count": "1",
        "cache_hit": "false",
        "cache_key": cache_key,
        "review_reason": review_reason,
        "lipinski_source": lipinski_source,
        "is_pains_positive": str(is_pains).lower(),
    }

    confidence = 0.97
    member_map = build_member_map(candidate, members, result, "matched", confidence)

    created_at = datetime.now(timezone.utc).isoformat()
    cache_payload = {
        "cache_key": cache_key,
        "candidate_id": candidate.get("compound_candidate_id", ""),
        "candidate_key": candidate.get("candidate_key", ""),
        "candidate_status": candidate.get("candidate_status", ""),
        "search_payload": search_payload,
        "search_terms": [t.to_dict() for t in terms],
        "request_details": [],
        "source_usage": {
            "pubchem_requests": 0,
            "chembl_requests": 0,
            "pubchem_hits": 0,
            "chembl_hits": 0,
        },
        "ordered_hits": [],
        "result": result,
        "status": result["enrichment_status"],
        "review_reason": result.get("review_reason", ""),
        "confidence": confidence,
        "request_count": 0,
        "request_cache_hits": 0,
        "request_cache_misses": 0,
        "created_at": created_at,
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
        "request_count": 0,
        "request_cache_hits": 0,
        "request_cache_misses": 0,
        "selected_source_name": result.get("source_name", ""),
        "selected_identifier": result.get("inchi_key", ""),
        "selected_inchi_key": result.get("inchi_key", ""),
        "selected_pubchem_cid": "",
        "selected_chembl_id": "",
        "enrichment_confidence": result.get("enrichment_confidence", "0.0000"),
        "cache_file": str(cache_file),
        "search_terms_json": json.dumps(
            [t.to_dict() for t in terms], ensure_ascii=False
        ),
        "created_at": created_at,
    }
    return result, member_map, cache_index


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
            result.setdefault("evidence_type", "")
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

    # KNApSAcK source-structure anchor (primary accept path). Before any external
    # search: if a candidate member's KNApSAcK-published structure formula
    # corroborates the raw representative formula, that published structure IS the
    # compound's identity. Accept it directly, compute ADME inline, and skip the
    # PubChem/ChEMBL identity search entirely.
    anchor = knapsack_structure_for_candidate(candidate, members)
    if anchor is not None:
        matched_cid, ks_inchikey, ks_smiles, ks_formula = anchor
        result, member_map, cache_index = build_knapsack_anchor_result(
            candidate=candidate,
            members=members,
            terms=terms,
            search_payload=search_payload,
            cache_key=cache_key,
            cache_file=cache_file,
            matched_cid=matched_cid,
            inchi_key=ks_inchikey,
            smiles=ks_smiles,
            molecular_formula=ks_formula,
            review_row=review_row,
            settings=settings,
            logger=logger,
        )
        return result, member_map, cache_index, False

    cache_index_req_hits = 0
    cache_index_req_misses = 0
    source_usage = {
        "pubchem_requests": 0,
        "chembl_requests": 0,
        "pubchem_hits": 0,
        "chembl_hits": 0,
    }
    request_details: List[Dict[str, Any]] = []

    # Reliable-first fetch with early-exit. As soon as a source returns a hit that
    # already satisfies a single-source accept path (CAS or name signal WITH
    # formula agreement), stop: the accept decision is settled and further fetches
    # cannot change which identity is accepted or its structure. PubChem is queried
    # first; ChEMBL is only queried when PubChem did not already corroborate (which
    # is also where the cross-source InChIKey accept path can still fire).
    def _corroborated(hits: List[SourceHit]) -> bool:
        return any(_hit_accept_ready(candidate, terms, h) for h in hits)

    # One request budget spans both sources: a candidate that never corroborates
    # stops after settings.max_requests_per_candidate PubChem+ChEMBL requests
    # instead of exhausting every CAS/name term. Corroborated candidates hit the
    # stop_check first (~3-4 requests), so the budget never touches them.
    budget = RequestBudget(settings.max_requests_per_candidate)

    pubchem_hits, pubchem_meta = search_pubchem(
        candidate,
        terms,
        settings,
        logger,
        settings.cache_root,
        stop_check=_corroborated,
        budget=budget,
    )
    if _corroborated(pubchem_hits):
        chembl_hits: List[SourceHit] = []
        chembl_meta = {"source": "ChEMBL", "requests": []}
    else:
        chembl_hits, chembl_meta = search_chembl(
            candidate,
            terms,
            settings,
            logger,
            settings.cache_root,
            stop_check=_corroborated,
            budget=budget,
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

    # Gate identity on corroboration (formula agreement is the decisive check).
    # Accept only a corroborated hit; otherwise drop the structure and let 05
    # fall back to the raw name_formula/name/cas identity.
    decision = evaluate_identity(candidate, terms, ordered, cross_key)
    total_matches = len(all_hits)

    result = candidate_result_from_hit(
        candidate=candidate,
        best=decision.hit,
        second=second,
        status=decision.status,
        reason=decision.reason,
        search_terms=terms,
        cache_key=cache_key,
        cache_hit=False,
        source_usage=source_usage,
        run_id=stable_timestamp(settings.batch_id),
        settings=settings,
        total_matches=total_matches,
    )

    # Overwrite provenance with the corroboration verdict: an HONEST confidence
    # (high only when structurally corroborated), the strategy, and the evidence
    # type. This is what downstream (05) must consume instead of trusting that a
    # returned InChIKey means the identity is verified.
    result["match_strategy"] = decision.strategy
    result["evidence_type"] = decision.evidence_type
    result["enrichment_confidence"] = f"{decision.confidence:.4f}"
    result["enrichment_status"] = decision.status
    result["match_reason"] = ";".join(
        [x for x in [decision.reason, review_reason] if x]
    )
    result["match_rank"] = decision.rank
    result["match_count"] = decision.count
    if not decision.accepted and review_reason:
        result["review_reason"] = ";".join(
            [x for x in [review_reason, decision.reason] if x]
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
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help=(
            "Smoke/sample mode: enrich only the first N candidates. Overrides "
            "the ENRICH_LIMIT env var. Use for a small live-API check before the "
            "full run."
        ),
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

    global structure_by_cid
    structure_by_cid = load_structure_by_cid(
        ETL_ROOT / "knapsack" / "out" / "plants_compounds.csv"
    )
    logger.info(
        "Loaded %d KNApSAcK source structures for the identity anchor",
        len(structure_by_cid),
    )

    candidate_rows, members_by_candidate, review_by_candidate = load_candidate_inputs(
        settings
    )

    limit = args.limit if args.limit is not None else settings.enrich_limit
    if limit and limit > 0 and limit < len(candidate_rows):
        logger.info(
            "Smoke/sample mode: enriching first %d of %d candidates",
            limit,
            len(candidate_rows),
        )
        candidate_rows = candidate_rows[:limit]

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
