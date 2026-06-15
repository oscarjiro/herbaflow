# backend/scripts/golden/capture_gd1.py
"""Record the deterministic GD-1 golden fixtures (curcumin x colorectal cancer).

ONE-OFF, NOT part of CI: rerun only to refresh fixtures. It reads the live database
(canonical curcumin compound + its measured compound-target edges + the colorectal-cancer
disease-target snapshot) and makes ONE live call each to STRING and g:Profiler, then writes
five JSON fixtures into ``backend/tests/scientific/fixtures/``. GD-1 inputs are public data, so
the fixtures are committed; the regression test seeds them into a throwaway Postgres and replays
the recorded STRING/g:Profiler responses so the run is fully offline and deterministic.

Run from ``backend/``::

    uv run python scripts/golden/capture_gd1.py

Identifiers (confirmed against the live DB at capture time):
  - curcumin compound_id = bbcfd2c2-1d5e-5a46-85c6-f1fa45b9bc9f (ChEMBL140)
  - curcumin InChIKey     = VFLDPWHFBUODDF-FCXRPNKRSA-N
  - colorectal cancer disease_id = 37d4f6a9-1969-5cca-9056-df6b65a8dbec (DOID:9256)

The default Stage-3/4/6/8 parameters all come from the shared contract via ``app.contracts``;
this script reads them rather than hardcoding so the fixtures track the contract.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

import asyncpg
import httpx

# Run as a script (`python scripts/golden/capture_gd1.py`) puts scripts/ on sys.path, not the
# backend root, so make `app` importable before importing it (mirrors scripts/dump_openapi.py).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from app import contracts  # noqa: E402
from app.integrations.gprofiler import GprofilerClient  # noqa: E402
from app.integrations.string_db import StringClient  # noqa: E402

CURCUMIN_ID = "bbcfd2c2-1d5e-5a46-85c6-f1fa45b9bc9f"
DISEASE_ID = "37d4f6a9-1969-5cca-9056-df6b65a8dbec"

FIXTURES = Path(__file__).resolve().parents[2] / "tests" / "scientific" / "fixtures"


def _database_url() -> str:
    url = os.environ.get("DATABASE_URL")
    if not url:
        # Fall back to the project .env (DATABASE_URL is the live Supabase pooler URI).
        env = Path(__file__).resolve().parents[3] / ".env"
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("DATABASE_URL="):
                url = line.split("=", 1)[1].strip()
                break
    if not url:
        raise RuntimeError("DATABASE_URL not set and not found in .env")
    # asyncpg wants a bare postgres:// DSN (strip any SQLAlchemy +asyncpg suffix).
    return url.replace("postgresql+asyncpg://", "postgresql://")


async def _fetch_seed(conn: asyncpg.Connection) -> dict[str, Any]:
    """Read the canonical curcumin compound, its measured edges, the targets they reference,
    and the colorectal-cancer disease-target snapshot at the default Stage-4 floor."""
    min_score = float(contracts.disease_targets_defaults()["min_score"])

    compound = await conn.fetchrow(
        """
        SELECT compound_id, canonical_key, canonical_name, inchi_key,
               molecular_weight, logp, hbond_donors, hbond_acceptors,
               tpsa, rotatable_bonds, num_ro5_violations, validation_status
        FROM compounds WHERE compound_id = $1
        """,
        CURCUMIN_ID,
    )
    if compound is None:
        raise RuntimeError(f"curcumin compound {CURCUMIN_ID} not found")

    # Curcumin's measured edges + discovery params (these decide D9 reuse).
    edge_rows = await conn.fetch(
        """
        SELECT ct.compound_id, ct.target_id, ct.prediction_method, ct.score,
               ct.pchembl_value, ct.source_id, ct.source_url,
               ct.min_pchembl, ct.min_assay_confidence
        FROM compound_targets ct
        WHERE ct.compound_id = $1
        ORDER BY ct.target_id
        """,
        CURCUMIN_ID,
    )

    # Disease-target snapshot at the default floor (Stage-4 read shape).
    dt_rows = await conn.fetch(
        """
        SELECT dt.disease_id, dt.target_id, dt.opentargets_score,
               dt.association_type, dt.source_id, dt.source_url
        FROM disease_targets dt
        WHERE dt.disease_id = $1 AND dt.opentargets_score >= $2
        ORDER BY dt.opentargets_score DESC, dt.target_id
        """,
        DISEASE_ID,
        min_score,
    )

    # The DISTINCT targets referenced by either side (seed must insert these so the FK reads work).
    referenced = {str(r["target_id"]) for r in edge_rows} | {str(r["target_id"]) for r in dt_rows}
    target_rows = await conn.fetch(
        """
        SELECT target_id, canonical_key, gene_symbol, uniprot_accession
        FROM targets WHERE target_id = ANY($1::uuid[])
        ORDER BY gene_symbol NULLS LAST, target_id
        """,
        list(referenced),
    )

    compound_targets = [
        {
            "compound_id": str(r["compound_id"]),
            "target_id": str(r["target_id"]),
            "prediction_method": r["prediction_method"],
            "score": r["score"],
            "pchembl_value": r["pchembl_value"],
            "source_id": str(r["source_id"]) if r["source_id"] is not None else None,
            "source_url": r["source_url"],
            "min_pchembl": r["min_pchembl"],
            "min_assay_confidence": r["min_assay_confidence"],
        }
        for r in edge_rows
    ]
    disease_targets = [
        {
            "disease_id": str(r["disease_id"]),
            "target_id": str(r["target_id"]),
            "opentargets_score": r["opentargets_score"],
            "association_type": r["association_type"],
            "source_id": str(r["source_id"]) if r["source_id"] is not None else None,
            "source_url": r["source_url"],
        }
        for r in dt_rows
    ]
    targets = [
        {
            "target_id": str(r["target_id"]),
            "canonical_key": r["canonical_key"],
            "gene_symbol": r["gene_symbol"],
            "uniprot_accession": r["uniprot_accession"],
        }
        for r in target_rows
    ]

    # ChEMBL replay backstop: the measured (ChEMBL) edges as ChemblHit-shaped rows, keyed by
    # accession. Used ONLY if D9 edge-reuse does not fire (it does, for the default params).
    by_target = {t["target_id"]: t for t in targets}
    chembl_hits = [
        {
            "uniprot_accession": by_target[e["target_id"]]["uniprot_accession"],
            "pchembl_value": e["pchembl_value"],
            "activity_type": "measured",
        }
        for e in compound_targets
        if e["prediction_method"] == "chembl_bioactivity" and e["pchembl_value"] is not None
    ]

    seed = {
        "curcumin_compound_id": CURCUMIN_ID,
        "disease_id": DISEASE_ID,
        "curcumin_inchikey": compound["canonical_key"],
        "compound": {
            "compound_id": str(compound["compound_id"]),
            "canonical_key": compound["canonical_key"],
            "canonical_name": compound["canonical_name"],
            "inchi_key": compound["inchi_key"],
            "molecular_weight": compound["molecular_weight"],
            "logp": compound["logp"],
            "hbond_donors": compound["hbond_donors"],
            "hbond_acceptors": compound["hbond_acceptors"],
            "tpsa": compound["tpsa"],
            "rotatable_bonds": compound["rotatable_bonds"],
            "num_ro5_violations": compound["num_ro5_violations"],
            "validation_status": compound["validation_status"],
        },
        "targets": targets,
        "compound_targets": compound_targets,
        "disease_targets": disease_targets,
        "chembl_hits": chembl_hits,
        "stage3_params": contracts.target_defaults(),
        "stage4_params": contracts.disease_targets_defaults(),
    }
    return seed


def _overlap_symbols(seed: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The Stage-5 overlap gene symbols (S3 target_ids ∩ S4 target_ids -> gene_symbol, first-seen
    order) and the full Stage-3 universe gene symbols (the g:Profiler custom background)."""
    by_target = {t["target_id"]: t for t in seed["targets"]}
    s3_target_ids: list[str] = []
    seen_s3: set[str] = set()
    for e in seed["compound_targets"]:
        tid = e["target_id"]
        if tid not in seen_s3:
            seen_s3.add(tid)
            s3_target_ids.append(tid)
    s4_target_ids = {e["target_id"] for e in seed["disease_targets"]}

    overlap: list[str] = []
    seen_sym: set[str] = set()
    for tid in s3_target_ids:
        if tid in s4_target_ids:
            sym = by_target[tid]["gene_symbol"]
            if sym and sym not in seen_sym:
                seen_sym.add(sym)
                overlap.append(sym)

    background: list[str] = []
    seen_bg: set[str] = set()
    for tid in s3_target_ids:
        sym = by_target[tid]["gene_symbol"]
        if sym and sym not in seen_bg:
            seen_bg.add(sym)
            background.append(sym)
    return overlap, background


async def _capture_string(overlap: list[str]) -> list[dict[str, Any]]:
    """One live STRING network call over the overlap symbols at the Stage-6 defaults."""
    ppi = contracts.ppi_defaults()
    async with httpx.AsyncClient() as http:
        edges = await StringClient(http).network(
            overlap,
            min_confidence=float(ppi["min_confidence"]),
            network_type=str(ppi["network_type"]),
        )
    return [{"source": e.source, "target": e.target, "confidence": e.confidence} for e in edges]


async def _capture_gprofiler(overlap: list[str], background: list[str]) -> list[dict[str, Any]]:
    """One live g:Profiler enrichment call: query = overlap, background = Stage-3 universe."""
    en = contracts.enrichment_defaults()
    async with httpx.AsyncClient() as http:
        terms = await GprofilerClient(http).profile(
            query=overlap,
            background=background,
            sources=list(en["sources"]),
            correction=str(en["correction"]),
            user_threshold=float(en["significance_threshold"]),
            no_iea=bool(en["no_iea"]),
        )
    return [
        {
            "source": t.source,
            "native": t.native,
            "name": t.name,
            "p_value": t.p_value,
            "term_size": t.term_size,
            "query_size": t.query_size,
            "intersection_size": t.intersection_size,
            "intersection": t.intersection,
            "significant": t.significant,
        }
        for t in terms
    ]


def _write(name: str, payload: Any) -> None:
    FIXTURES.mkdir(parents=True, exist_ok=True)
    (FIXTURES / name).write_text(
        json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=False) + "\n",
        encoding="utf-8",
    )


async def main() -> None:
    conn = await asyncpg.connect(_database_url())
    try:
        seed = await _fetch_seed(conn)
    finally:
        await conn.close()

    overlap, background = _overlap_symbols(seed)

    string_edges = await _capture_string(overlap)
    gprofiler_terms = await _capture_gprofiler(overlap, background)

    _write("gd1_seed.json", seed)
    _write("gd1_string_network.json", string_edges)
    _write("gd1_gprofiler.json", gprofiler_terms)

    has_crc = any("colorectal cancer" in t["name"].lower() for t in gprofiler_terms)
    print("GD-1 capture complete")
    print(f"  curcumin compound_id : {seed['curcumin_compound_id']}")
    print(f"  curcumin InChIKey    : {seed['curcumin_inchikey']}")
    print(f"  disease_id           : {seed['disease_id']}")
    print(f"  seed targets         : {len(seed['targets'])}")
    print(f"  compound_targets     : {len(seed['compound_targets'])}")
    print(f"  disease_targets      : {len(seed['disease_targets'])}")
    print(f"  Stage-3 universe     : {len(background)} gene symbols")
    print(f"  overlap count        : {len(overlap)}")
    print(f"  overlap symbols      : {', '.join(overlap)}")
    print(f"  STRING edges         : {len(string_edges)}")
    print(f"  g:Profiler terms     : {len(gprofiler_terms)}")
    print(f"  'Colorectal cancer' in term names : {has_crc}")


if __name__ == "__main__":
    asyncio.run(main())
