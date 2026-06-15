# backend/scripts/golden/capture_gd2.py
"""Record the deterministic GD-2 golden fixtures (Hito 3-plant x pancreatic cancer).

ONE-OFF, NOT part of CI: rerun only to refresh fixtures; depends on the gitignored Hito
source data (an unpublished thesis). It reads the four cleaned Hito CSVs, deterministically
assigns a synthetic ``target_id`` per gene symbol (UUID v5 over a fixed namespace, so the
same symbol always maps to the same id and the plant/disease/overlap id-lists stay
consistent), and makes ONE live STRING call over the computed plant-disease overlap, then
writes four JSON fixtures into ``backend/tests/scientific/fixtures/``.

GD-2 is INPUT-CONTROLLED: the regression test feeds these exact target id-lists through the
``manual_targets`` / ``manual_disease_targets`` entry modes, which only verify each target
exists and load the rows (NO live ChEMBL/UniProt/OpenTargets at run time), then runs
Stages 5->8 and compares Herbaflow's top-10 MCC hubs to Hito's reported top-10.

Because Hito's thesis data is UNPUBLISHED, every ``gd2_*.json`` fixture is gitignored: only
this CODE is committed.

Run from ``backend/``::

    uv run python scripts/golden/capture_gd2.py

The Stage-6 (``ppi``) STRING parameters come from the shared contract via ``app.contracts``;
this script reads them rather than hardcoding so the fixtures track the contract.
"""

from __future__ import annotations

import asyncio
import csv
import json
import sys
import uuid
from pathlib import Path
from typing import Any

import httpx

# Run as a script (`python scripts/golden/capture_gd2.py`) puts scripts/ on sys.path, not the
# backend root, so make `app` importable before importing it (mirrors capture_gd1.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import contracts  # noqa: E402
from app.integrations.string_db import StringClient  # noqa: E402

# Fixed namespace so target_id = uuid5(GD2_NS, gene_symbol) is reproducible across runs and
# consistent across the plant/disease/overlap id-lists (same symbol -> same id everywhere).
GD2_NS = uuid.UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8")

# The cleaned Hito source data (gitignored, under .superpowers/).
SOURCE = (
    Path(__file__).resolve().parents[3]
    / ".superpowers"
    / "audit-session-3"
    / "phase-7-thesis-data"
    / "clean"
)

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "scientific" / "fixtures"


def _target_id(symbol: str) -> str:
    return str(uuid.uuid5(GD2_NS, symbol))


def _read_symbols(filename: str) -> list[str]:
    """Read the ``gene_symbol`` column from a clean CSV, in file order, de-duplicated."""
    path = SOURCE / filename
    out: list[str] = []
    seen: set[str] = set()
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            sym = (row.get("gene_symbol") or "").strip()
            if sym and sym not in seen:
                seen.add(sym)
                out.append(sym)
    return out


def _read_hub_ref() -> list[dict[str, Any]]:
    """Hito's reported top-10 hubs (rank + 4 normalized centralities + his mean score)."""
    path = SOURCE / "gd2_hub_genes_ref.csv"
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8-sig", newline="") as fh:
        for row in csv.DictReader(fh):
            out.append(
                {
                    "rank": int(row["rank"]),
                    "gene_symbol": row["gene_symbol"].strip(),
                    "degree": float(row["degree"]),
                    "betweenness": float(row["betweenness"]),
                    "closeness": float(row["closeness"]),
                    "eigenvector": float(row["eigenvector"]),
                    "score": float(row["score"]),
                }
            )
    return out


def _build_seed() -> tuple[dict[str, Any], list[dict[str, Any]], list[str], list[str]]:
    plant_symbols = _read_symbols("gd2_plant_targets.csv")
    disease_symbols = _read_symbols("gd2_disease_targets.csv")
    overlap_ref_symbols = _read_symbols("gd2_overlap_ref.csv")
    hub_ref = _read_hub_ref()
    hub_symbols = [h["gene_symbol"] for h in hub_ref]

    # Computed overlap = plant ∩ disease by symbol (preserve plant order). Expected 247.
    disease_set = set(disease_symbols)
    overlap_247_symbols = [s for s in plant_symbols if s in disease_set]

    # Union of every referenced symbol -> the seeded Target rows.
    union_symbols: list[str] = []
    seen: set[str] = set()
    for group in (plant_symbols, disease_symbols, overlap_ref_symbols, hub_symbols):
        for sym in group:
            if sym not in seen:
                seen.add(sym)
                union_symbols.append(sym)

    targets = [
        {
            "target_id": _target_id(sym),
            # Synthetic but unique; accession left null (the pipeline keys on gene_symbol).
            "canonical_key": f"uniprot:GD2-{sym}",
            "gene_symbol": sym,
        }
        for sym in union_symbols
    ]

    seed = {
        "_note": (
            "GD-2 deterministic seed from Hito's unpublished thesis data. "
            "target_id = uuid5(GD2_NS, gene_symbol); accession is null by design "
            "(manual_targets / manual_disease_targets key on gene_symbol)."
        ),
        "targets": targets,
        "plant_target_ids": [_target_id(s) for s in plant_symbols],
        "disease_target_ids": [_target_id(s) for s in disease_symbols],
        "overlap_233_ids": [_target_id(s) for s in overlap_ref_symbols],
        "overlap_233_symbols": overlap_ref_symbols,
        # Fed on BOTH sides for the headline run -> overlap is exactly the 233 set.
        "headline_target_ids": [_target_id(s) for s in overlap_ref_symbols],
        "gd2_overlap_247_symbols": overlap_247_symbols,
        "n_plant": len(plant_symbols),
        "n_disease": len(disease_symbols),
        "n_overlap_ref": len(overlap_ref_symbols),
        "n_overlap_247": len(overlap_247_symbols),
        "n_union": len(union_symbols),
    }
    return seed, hub_ref, overlap_ref_symbols, overlap_247_symbols


async def _capture_string(symbols: list[str]) -> list[dict[str, Any]]:
    """One live STRING network call over the overlap symbols at the Stage-6 defaults."""
    ppi = contracts.ppi_defaults()
    async with httpx.AsyncClient() as http:
        edges = await StringClient(http).network(
            symbols,
            min_confidence=float(ppi["min_confidence"]),
            network_type=str(ppi["network_type"]),
        )
    return [{"source": e.source, "target": e.target, "confidence": e.confidence} for e in edges]


def _write(name: str, payload: Any) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


async def main() -> None:
    seed, hub_ref, overlap_233_symbols, overlap_247_symbols = _build_seed()

    set_233 = set(overlap_233_symbols)
    set_247 = set(overlap_247_symbols)
    subset_ok = set_233 <= set_247
    extra = sorted(set_247 - set_233)

    # STRING is captured ONCE over the 247-gene computed overlap. The 233-gene headline network
    # equals this network filtered to edges whose BOTH endpoints are in the 233 set, so the
    # replay can derive the headline from the same recording.
    string_edges = await _capture_string(overlap_247_symbols)
    string_nodes = sorted({e["source"] for e in string_edges} | {e["target"] for e in string_edges})

    hub_ref_payload = {
        "hub_genes": hub_ref,
        "overlap_233": overlap_233_symbols,
    }
    snapshot = {
        "_note": "headline_mcc_top10 reconciled by the GD-2 regression test",
        "headline_overlap": 233,
        "secondary_overlap": 247,
        "ranking_metric": "mcc",
        "headline_mcc_top10": [],
    }

    _write("gd2_seed.json", seed)
    _write("gd2_string.json", string_edges)
    _write("gd2_hub_ref.json", hub_ref_payload)
    _write("gd2_snapshot.json", snapshot)

    print("GD-2 capture complete")
    print(f"  union targets        : {seed['n_union']}")
    print(f"  plant targets        : {seed['n_plant']}")
    print(f"  disease targets      : {seed['n_disease']}")
    print(f"  overlap (Hito ref)   : {seed['n_overlap_ref']}")
    print(f"  overlap (computed)   : {seed['n_overlap_247']}")
    print(f"  233 subset of 247    : {subset_ok}")
    print(f"  |247 \\ 233|          : {len(extra)} (expect 14) -> {', '.join(extra)}")
    print(f"  STRING nodes         : {len(string_nodes)}")
    print(f"  STRING edges         : {len(string_edges)}")
    print(
        "  fixtures written     : "
        "gd2_seed.json, gd2_string.json, gd2_hub_ref.json, gd2_snapshot.json"
    )


if __name__ == "__main__":
    asyncio.run(main())
