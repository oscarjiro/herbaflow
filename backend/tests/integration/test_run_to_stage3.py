"""Integration: drive a guided run S1 -> S2 -> S3 through the real engine.

Uses the HTTP ``client`` fixture (in-process ASGI + real Postgres). The Stage-3
external clients are faked by monkeypatching the classes in the ``stage3`` module
namespace, so ``stage3.run`` (no injected clients) picks the fakes up. The run is
driven create -> advance -> advance, then a Stage-3 param Redo (``reset-from/3``)
proves Stage 3 re-runs alone (no S4+).
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.chembl import ChemblHit
from app.integrations.uniprot import UniProtReason, UniProtRecord, UniProtResolution
from app.pipeline.stages import stage3

# Stages that have settled (terminal or paused). Includes the Stage-3 checkpoint.
SETTLED = frozenset(
    {
        "complete",
        "failed",
        "stage_1_awaiting_approval",
        "stage_2_awaiting_approval",
        "stage_3_awaiting_approval",
    }
)


class _FakeChembl:
    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence):
        # A hit for any non-empty InChIKey; none otherwise.
        return [ChemblHit("P04637", 6.5, "IC50")] if ik else []


class _FakePubchem:
    async def active_targets_for_inchikey(self, ik):
        return []


class _FakeUniProt:
    async def resolve(self, acc):
        if acc == "P04637":
            return UniProtResolution(UniProtRecord(acc, "TP53", "p53"), None)
        return UniProtResolution(None, UniProtReason.NO_HUMAN_RECORD)


async def _poll(c, run_id: str, *, until=None, max_iters: int = 80) -> dict:
    """Poll GET /analyses/{id} until settled (or a specific status is reached)."""
    final: dict = {}
    for _ in range(max_iters):
        final = (await c.get(f"/analyses/{run_id}")).json()
        st = final.get("status")
        if until is not None and st == until:
            break
        if until is None and st in SETTLED:
            break
    return final


@pytest.mark.asyncio
async def test_guided_run_reaches_stage3_and_param_redo_reruns_s3_only(
    client, engine, monkeypatch
) -> None:
    c, ids = client

    # Fake the Stage-3 clients in the stage3 namespace so the un-injected path uses them.
    monkeypatch.setattr(stage3, "ChemblClient", lambda http: _FakeChembl())
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", lambda http: _FakePubchem())
    monkeypatch.setattr(stage3, "UniProtClient", lambda http: _FakeUniProt())

    # Seed the source rows (the integration migrations do not apply them) and give the
    # screened compounds a non-NULL InChIKey (compute() reports coverage 0 without one).
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await s.execute(
            text(
                "insert into source_systems(source_name, source_type) values "
                "('ChEMBL', 'api'),('PubChem BioAssay', 'api'),('UniProt', 'api') "
                "on conflict (source_name) do nothing"
            )
        )
        await s.execute(
            text("update compounds set inchi_key = 'IKX' where compound_id in (:c1, :c2)"),
            {"c1": ids["c1"], "c2": ids["c2"]},
        )
        await s.commit()

    # Create a guided run on the full plant (c1 + c2) and walk S1 -> S2 -> S3.
    resp = await c.post(
        "/analyses",
        json={
            "plant_ids": [str(ids["plant_full"])],
            "disease_id": str(ids["disease"]),
            "mode": "guided",
        },
    )
    assert resp.status_code == 202
    run_id = resp.json()["analysis_id"]

    state = await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert state["status"] == "stage_1_awaiting_approval"

    adv1 = await c.post(f"/analyses/{run_id}/advance")
    assert adv1.status_code == 202
    # Non-blocking proof: advance returns immediately with the *_running start state; the
    # slow stage runs in a BackgroundTask (the prior committed status is no longer returned).
    assert adv1.json()["status"] == "stage_2_running"
    state = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert state["status"] == "stage_2_awaiting_approval"
    assert state["stage_results"]["2"]["count"] == 2

    adv2 = await c.post(f"/analyses/{run_id}/advance")
    assert adv2.status_code == 202
    assert adv2.json()["status"] == "stage_3_running"
    state = await _poll(c, run_id, until="stage_3_awaiting_approval")
    assert state["status"] == "stage_3_awaiting_approval", "guided run must checkpoint at S3"

    # Stage-3 result shape: a tagged target list + a reported coverage_pct.
    s3 = state["stage_results"]["3"]
    assert "coverage_pct" in s3
    target_ids = {t["target_id"] for t in s3["targets"]}
    p04637_id = canonical_target_id_for("P04637")
    assert p04637_id in target_ids, "P04637 target must be present in the S3 result"

    # Persistence: a P04637 target row (gene_symbol TP53) and a chembl_bioactivity edge.
    async with maker() as s:
        gene = (
            await s.execute(
                text("select gene_symbol from targets where canonical_key = 'uniprot:P04637'")
            )
        ).scalar_one()
        assert gene == "TP53"
        method = (
            await s.execute(
                text(
                    "select prediction_method from compound_targets "
                    "where prediction_method = 'chembl_bioactivity' limit 1"
                )
            )
        ).scalar_one()
        assert method == "chembl_bioactivity"

    # Stage-3 param Redo: reset-from/3 with an override re-runs S3 ONLY (no S4+).
    reset = await c.post(
        f"/analyses/{run_id}/reset-from/3",
        json={"parameters": {"3": {"min_pchembl": 6.0}}},
    )
    assert reset.status_code == 202
    assert reset.json()["status"] == "stage_3_running"
    state = await _poll(c, run_id, until="stage_3_awaiting_approval")
    assert state["status"] == "stage_3_awaiting_approval"

    results = state["stage_results"]
    assert "3" in results, "S3 must be refreshed after the param Redo"
    assert "coverage_pct" in results["3"]
    assert not any(k in results for k in ("4", "5", "6", "7", "8")), "no downstream stages re-ran"
    assert state["parameters"]["target"]["min_pchembl"] == 6.0


def canonical_target_id_for(accession: str) -> str:
    """The deterministic target_id the resolver derives from a UniProt accession."""
    from app.services import canonical

    key = canonical.target_canonical_key(uniprot=accession)
    return canonical.target_id_from_key(key)


@pytest.mark.asyncio
async def test_replace_for_compound_roundtrips_discovery_params(
    session, seed_compound, seed_target
) -> None:
    """replace_for_compound writes an edge carrying the discovery params; edges_for_compound
    reads it back joined to the target; a subsequent empty replace clears the set (D9)."""
    from app.repositories.compound_target import CompoundTargetRepository

    repo = CompoundTargetRepository(session)
    await repo.replace_for_compound(
        seed_compound,
        [
            {
                "target_id": str(seed_target),
                "prediction_method": "chembl_bioactivity",
                "pchembl_value": 6.5,
                "score": 6.5,
                "source_url": "https://example/p",
                "min_pchembl": 5.0,
                "min_assay_confidence": 7,
            }
        ],
    )
    await session.commit()

    edges = await repo.edges_for_compound(seed_compound)
    assert len(edges) == 1
    e = edges[0]
    assert e["target_id"] == str(seed_target)
    assert e["prediction_method"] == "chembl_bioactivity"
    assert e["pchembl_value"] == 6.5
    assert e["min_pchembl"] == 5.0
    assert e["min_assay_confidence"] == 7
    assert e["gene_symbol"] == "CTGENE"  # joined from the seeded target

    # Replacing with an empty set drops every existing edge for the compound.
    await repo.replace_for_compound(seed_compound, [])
    await session.commit()
    assert await repo.edges_for_compound(seed_compound) == []


class _RaiseChembl:
    async def targets_for_inchikey(self, ik, *, min_pchembl, min_confidence):
        raise AssertionError("ChEMBL must not be called when the compound's edges are reused")


class _RaisePubchem:
    async def active_targets_for_inchikey(self, ik):
        raise AssertionError("PubChem must not be called when the compound's edges are reused")


class _RaiseUniProt:
    async def resolve(self, acc):
        raise AssertionError("UniProt must not be called when the compound's edges are reused")


@pytest.mark.asyncio
async def test_stage3_reuses_cached_edges_and_refetches_on_param_change(engine, seeded) -> None:
    """A compound whose persisted edges match the run's discovery params is reused without any
    external call; tightening assay confidence forces a refetch (D9)."""
    from app.pipeline.stages import stage3
    from app.repositories.compound_target import CompoundTargetRepository
    from app.services import canonical

    maker = async_sessionmaker(engine, expire_on_commit=False)
    cid = str(seeded["c1"])
    acc = "P04637"
    tid = canonical_target_id_for(acc)

    # Seed: a source row, a human target, and a cached edge discovered at (min_pchembl 5.0, conf 7).
    async with maker() as s:
        await s.execute(
            text(
                "insert into source_systems(source_name, source_type) values "
                "('ChEMBL', 'api'),('PubChem BioAssay', 'api'),('UniProt', 'api') "
                "on conflict (source_name) do nothing"
            )
        )
        await s.execute(
            text("update compounds set inchi_key = 'IKX' where compound_id = :c"),
            {"c": seeded["c1"]},
        )
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol, uniprot_accession) "
                "values (:t, :k, 'TP53', :a)"
            ),
            {"t": tid, "k": canonical.target_canonical_key(uniprot=acc), "a": acc},
        )
        repo = CompoundTargetRepository(s)
        await repo.replace_for_compound(
            seeded["c1"],
            [
                {
                    "target_id": tid,
                    "prediction_method": "chembl_bioactivity",
                    "pchembl_value": 6.5,
                    "score": 6.5,
                    "source_url": f"https://www.uniprot.org/uniprotkb/{acc}/entry",
                    "min_pchembl": 5.0,
                    "min_assay_confidence": 7,
                }
            ],
        )
        await s.commit()

    step2_passed = [{"compound_id": cid}]

    # Compatible params -> reuse: the raise-if-called fakes must never be invoked.
    async with maker() as s:
        result = await stage3.run(
            s,
            step2_passed,
            {"min_pchembl": 5.0, "min_assay_confidence": 7},
            chembl=_RaiseChembl(),
            pubchem=_RaisePubchem(),
            uniprot=_RaiseUniProt(),
        )
        await s.commit()
    assert {t["target_id"] for t in result["targets"]} == {tid}
    assert result["per_compound"][cid]["coverage"] == 1
    edge = next(e for e in result["compound_targets"] if e["compound_id"] == cid)
    assert edge["prediction_method"] == "chembl_bioactivity"

    # Stricter assay confidence (9 != 7) -> refetch: the fakes ARE called now.
    async with maker() as s:
        with pytest.raises(AssertionError, match="must not be called"):
            await stage3.run(
                s,
                step2_passed,
                {"min_pchembl": 5.0, "min_assay_confidence": 9},
                chembl=_RaiseChembl(),
                pubchem=_RaisePubchem(),
                uniprot=_RaiseUniProt(),
            )
