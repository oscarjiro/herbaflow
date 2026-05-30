"""Build the offline HGNC gene-symbol normalization map.

Downloads (or reads) hgnc_complete_set.txt and writes
backend/data/hgnc/hgnc_symbol_map.json.gz:
  UPPER(symbol|prev_symbol|alias_symbol) -> {"symbol": <approved>, "kind": approved|prev|alias}

Precedence on key collision: approved > prev > alias.

Usage (from backend/):
  uv run python scripts/build_hgnc_map.py                # download from genenames.org
  uv run python scripts/build_hgnc_map.py --input PATH   # use a local TSV (offline)
"""
from __future__ import annotations

import argparse
import csv
import gzip
import io
import json
import sys
import urllib.request
from pathlib import Path

HGNC_URL = (
    "https://storage.googleapis.com/public-download-files/hgnc/tsv/tsv/"
    "hgnc_complete_set.txt"
)
OUT_PATH = Path(__file__).resolve().parents[1] / "data" / "hgnc" / "hgnc_symbol_map.json.gz"

_PRECEDENCE = {"alias": 0, "prev": 1, "approved": 2}


def _read_tsv(input_path: str | None) -> str:
    if input_path:
        return Path(input_path).read_text(encoding="utf-8")
    with urllib.request.urlopen(HGNC_URL, timeout=60) as resp:  # noqa: S310
        return resp.read().decode("utf-8")


def build_map(tsv_text: str) -> dict[str, dict[str, str]]:
    reader = csv.DictReader(io.StringIO(tsv_text), delimiter="\t")
    out: dict[str, dict[str, str]] = {}

    def put(key: str, symbol: str, kind: str) -> None:
        key = key.strip().upper()
        if not key:
            return
        existing = out.get(key)
        if existing is None or _PRECEDENCE[kind] > _PRECEDENCE[existing["kind"]]:
            out[key] = {"symbol": symbol, "kind": kind}

    for row in reader:
        approved = (row.get("symbol") or "").strip()
        if not approved:
            continue
        put(approved, approved, "approved")
        for prev in (row.get("prev_symbol") or "").split("|"):
            if prev.strip():
                put(prev, approved, "prev")
        for alias in (row.get("alias_symbol") or "").split("|"):
            if alias.strip():
                put(alias, approved, "alias")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=None, help="Local hgnc_complete_set.txt (else download)")
    ap.add_argument("--out", default=str(OUT_PATH))
    args = ap.parse_args()

    tsv = _read_tsv(args.input)
    mapping = build_map(tsv)
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wt", encoding="utf-8") as fh:
        json.dump(mapping, fh, separators=(",", ":"))
    print(f"Wrote {len(mapping)} keys -> {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
