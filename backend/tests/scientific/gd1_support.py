"""Shared support for the GD-1 curcumin x colorectal-cancer golden regression.

One home for the deterministic, OFFLINE Level-A harness pieces so the regression test and the GD-1
report driver replay the SAME recorded ground truth:

- ``gd1_string_client`` / ``gd1_gprofiler_client`` build the shared ``ReplayString`` /
  ``ReplayGprofiler`` doubles over the recorded STRING + g:Profiler fixtures (no network).
- ``seed_gd1(engine)`` inserts the captured canonical data (curcumin, 835 targets, 104 measured
  edges, the CRC disease, 746 disease->target associations) and returns the seed dict.
- ``patch_gd1(monkeypatch)`` swaps the live STRING/g:Profiler clients for the replay doubles, and
  installs raise-if-called guards on the Stage-3 external clients to PROVE the D9 edge-reuse path
  keeps the run fully offline (every seeded curcumin edge was discovered at the run's default
  discovery params, so Stage 3 finds ``to_fetch == []`` and never constructs an external client).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.integrations.gprofiler import EnrichedTerm
from app.pipeline.stages import stage6, stage8
from tests.scientific.conftest import load_json
from tests.scientific.replay import ReplayGprofiler, ReplayString, forbid_stage3_clients

# Canonical CRC disease identity (the seed carries only disease_id; DOID 9256 = colorectal cancer).
_CRC_CANONICAL_KEY = "doid:9256"
_CRC_NAME = "Colorectal Cancer"


def gd1_string_client() -> ReplayString:
    """Replay the recorded STRING network (captured over the overlap, so the filter is a no-op)."""
    return ReplayString(load_json("gd1_string_network.json"))


def gd1_gprofiler_client() -> ReplayGprofiler:
    """Replay the recorded g:Profiler enrichment terms."""
    return ReplayGprofiler([EnrichedTerm(**t) for t in load_json("gd1_gprofiler.json")])


async def seed_gd1(engine: AsyncEngine) -> dict[str, Any]:
    """Insert the captured GD-1 canonical data and return the seed dict.

    Insert order respects the FK dependencies: source_systems (referenced by both edge tables) ->
    compounds -> targets -> compound_targets -> diseases -> disease_targets. All SQL is
    parameterized (``text()`` + bound params), mirroring the integration seed style.
    """
    seed = load_json("gd1_seed.json")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        # 1. source_systems — every distinct non-null source_id referenced by the edges must exist.
        source_ids: set[str] = set()
        for edge in seed["compound_targets"]:
            if edge.get("source_id"):
                source_ids.add(edge["source_id"])
        for edge in seed["disease_targets"]:
            if edge.get("source_id"):
                source_ids.add(edge["source_id"])
        for sid in source_ids:
            await s.execute(
                text(
                    "insert into source_systems(source_id, source_name, source_type) "
                    "values (:sid, :name, 'api') on conflict (source_id) do nothing"
                ),
                {"sid": sid, "name": f"gd1-source-{sid[:8]}"},
            )

        # 2. compounds — curcumin (BARE inchi_key; is_pains_positive + validation_status NOT NULL).
        comp = seed["compound"]
        await s.execute(
            text(
                "insert into compounds("
                "compound_id, canonical_key, canonical_name, inchi_key, molecular_weight, logp, "
                "hbond_donors, hbond_acceptors, tpsa, rotatable_bonds, num_ro5_violations, "
                "is_pains_positive, validation_status) values ("
                ":compound_id, :canonical_key, :canonical_name, :inchi_key, :molecular_weight, "
                ":logp, :hbond_donors, :hbond_acceptors, :tpsa, :rotatable_bonds, "
                ":num_ro5_violations, false, :validation_status)"
            ),
            {
                "compound_id": comp["compound_id"],
                "canonical_key": comp["canonical_key"],
                "canonical_name": comp["canonical_name"],
                "inchi_key": comp["inchi_key"],
                "molecular_weight": comp["molecular_weight"],
                "logp": comp["logp"],
                "hbond_donors": comp["hbond_donors"],
                "hbond_acceptors": comp["hbond_acceptors"],
                "tpsa": comp["tpsa"],
                "rotatable_bonds": comp["rotatable_bonds"],
                "num_ro5_violations": comp["num_ro5_violations"],
                "validation_status": comp["validation_status"],
            },
        )

        # 3. targets — all 835 canonical human proteins (multi-row executemany).
        await s.execute(
            text(
                "insert into targets("
                "target_id, canonical_key, gene_symbol, uniprot_accession, source_url) values "
                "(:target_id, :canonical_key, :gene_symbol, :uniprot_accession, :source_url)"
            ),
            [
                {
                    "target_id": t["target_id"],
                    "canonical_key": t["canonical_key"],
                    "gene_symbol": t.get("gene_symbol"),
                    "uniprot_accession": t.get("uniprot_accession"),
                    "source_url": t.get("source_url"),
                }
                for t in seed["targets"]
            ],
        )

        # 4. compound_targets — all 104 measured edges, with discovery params (D9 reuse keys).
        await s.execute(
            text(
                "insert into compound_targets("
                "compound_target_id, compound_id, target_id, source_id, prediction_method, "
                "score, pchembl_value, source_url, min_pchembl, min_assay_confidence) values ("
                ":compound_target_id, :compound_id, :target_id, :source_id, :prediction_method, "
                ":score, :pchembl_value, :source_url, :min_pchembl, :min_assay_confidence)"
            ),
            [
                {
                    "compound_target_id": uuid.uuid4(),
                    "compound_id": e["compound_id"],
                    "target_id": e["target_id"],
                    "source_id": e.get("source_id"),
                    "prediction_method": e["prediction_method"],
                    "score": e.get("score"),
                    "pchembl_value": e.get("pchembl_value"),
                    "source_url": e.get("source_url"),
                    "min_pchembl": e.get("min_pchembl"),
                    "min_assay_confidence": e.get("min_assay_confidence"),
                }
                for e in seed["compound_targets"]
            ],
        )

        # 5. diseases — the CRC row (canonical key DOID:9256, name from the canon).
        await s.execute(
            text(
                "insert into diseases(disease_id, canonical_key, disease_name) "
                "values (:disease_id, :canonical_key, :disease_name)"
            ),
            {
                "disease_id": seed["disease_id"],
                "canonical_key": _CRC_CANONICAL_KEY,
                "disease_name": _CRC_NAME,
            },
        )

        # 6. disease_targets — all 746 ETL-seeded associations (Stage 4 reads these).
        await s.execute(
            text(
                "insert into disease_targets("
                "disease_target_id, disease_id, target_id, source_id, association_type, "
                "opentargets_score, source_url) values ("
                ":disease_target_id, :disease_id, :target_id, :source_id, :association_type, "
                ":opentargets_score, :source_url)"
            ),
            [
                {
                    "disease_target_id": uuid.uuid4(),
                    "disease_id": e["disease_id"],
                    "target_id": e["target_id"],
                    "source_id": e.get("source_id"),
                    "association_type": e.get("association_type"),
                    "opentargets_score": e.get("opentargets_score"),
                    "source_url": e.get("source_url"),
                }
                for e in seed["disease_targets"]
            ],
        )

        await s.commit()
    return seed


def patch_gd1(monkeypatch: Any) -> None:
    """Swap STRING + g:Profiler for the replay doubles; forbid every Stage-3 external client.

    Only Stage 6 (STRING) and Stage 8 (g:Profiler) need replay: Stage 3 runs fully offline via D9
    edge-reuse (all 104 seeded curcumin edges carry the run's default discovery params). The
    raise-if-called guards on the Stage-3 clients PROVE that — if any trips, D9 did not fire.
    """
    monkeypatch.setattr(stage6, "StringClient", lambda http: gd1_string_client())
    monkeypatch.setattr(stage8, "GprofilerClient", lambda http: gd1_gprofiler_client())
    forbid_stage3_clients(monkeypatch)
