"""HGNC gene-symbol normalization (offline).

Resolves alias / previous gene symbols to the current approved HGNC symbol using a
prebuilt offline map (backend/data/hgnc/hgnc_symbol_map.json.gz). Never drops an input:
symbols absent from HGNC are returned upcased and flagged 'unrecognized'.

The map is built by backend/scripts/build_hgnc_map.py from genenames.org's
hgnc_complete_set.txt. If the map file is missing/unreadable, normalization degrades to
identity (everything 'unrecognized') and logs a warning — the pipeline never hard-fails.
"""

from __future__ import annotations

import gzip
import json
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

logger = logging.getLogger(__name__)

Status = Literal["approved", "alias_resolved", "prev_resolved", "unrecognized"]

# backend/app/services/gene_symbols.py -> parents[2] == backend/
_MAP_PATH = Path(__file__).resolve().parents[2] / "data" / "hgnc" / "hgnc_symbol_map.json.gz"

# Lazily-loaded lookup: UPPER(symbol|prev|alias) -> {"symbol": approved, "kind": ...}
_MAP: dict[str, dict[str, str]] | None = None

_KIND_TO_STATUS = {"approved": "approved", "prev": "prev_resolved", "alias": "alias_resolved"}


@dataclass(frozen=True)
class SymbolResult:
    input: str  # original, stripped
    canonical: str  # approved symbol, or upcased input if unrecognized
    status: Status


def _load_map(path: Path) -> dict[str, dict[str, str]]:
    try:
        with gzip.open(path, "rt", encoding="utf-8") as fh:
            data = json.load(fh)
        if not isinstance(data, dict):
            raise ValueError("HGNC map is not a JSON object")
        return data
    except (FileNotFoundError, OSError, ValueError) as exc:
        logger.warning("HGNC symbol map unavailable (%s); symbols will not be normalized", exc)
        return {}


def _get_map() -> dict[str, dict[str, str]]:
    global _MAP
    if _MAP is None:
        _MAP = _load_map(_MAP_PATH)
    return _MAP


def normalize(raw: str) -> SymbolResult:
    stripped = (raw or "").strip()
    key = stripped.upper()
    if not key:
        return SymbolResult(input=stripped, canonical="", status="unrecognized")
    entry = _get_map().get(key)
    if entry is None:
        return SymbolResult(input=stripped, canonical=key, status="unrecognized")
    status: Status = _KIND_TO_STATUS.get(entry.get("kind", "approved"), "alias_resolved")  # type: ignore[assignment]
    return SymbolResult(input=stripped, canonical=entry["symbol"], status=status)


def normalize_many(raws: Iterable[str]) -> list[SymbolResult]:
    return [normalize(r) for r in raws]
