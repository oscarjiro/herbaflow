"""Integration: SwissTargetPrediction (STP) paste-back import.

Drives a guided run to a settled Stage 3 (the run-to-S3 pattern: HTTP ``client``
fixture + monkeypatched Stage-3 clients + a non-NULL InChIKey), where the fake
ChEMBL returns a measured ``chembl_bioactivity`` hit for ``P04637`` on the
screened compound. Then exercises ``POST /analyses/{id}/import-stp-targets``:

- A predicted ``stp_import`` edge is written for the newly-resolved ``P99999``.
- The pre-existing measured ``P04637`` edge is reported ``skipped_measured`` and
  is NOT overwritten.
- The resolved STP targets are added to the run's Stage-3 set (tagged
  ``user-added``) and the edit re-runs from S5 (no Stage-4 stored result).
- A second import for the same compound REPLACES (not merges) its STP edges.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.integrations.chembl import ChemblHit
from app.integrations.uniprot import UniProtRecord
from app.pipeline.stages import stage3
from app.services import canonical

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
        # A measured hit for any non-empty InChIKey; none otherwise.
        return [ChemblHit("P04637", 6.5, "IC50")] if ik else []


class _FakePubchem:
    async def active_targets_for_inchikey(self, ik):
        return []


class _FakeUniProt:
    """Resolves the two STP accessions (P04637, P99999) as human records; else None."""

    def __init__(self, *_args, **_kwargs):
        pass

    async def resolve(self, acc):
        a = acc.strip().upper()
        if a == "P04637":
            return UniProtRecord(a, "TP53", "p53")
        if a == "P99999":
            return UniProtRecord(a, "GENE9", "protein nine")
        return None


async def _poll(c, run_id: str, *, until=None, max_iters: int = 80) -> dict:
    final: dict = {}
    for _ in range(max_iters):
        final = (await c.get(f"/analyses/{run_id}")).json()
        st = final.get("status")
        if until is not None and st == until:
            break
        if until is None and st in SETTLED:
            break
    return final


def _target_id_for(accession: str):
    key = canonical.target_canonical_key(uniprot=accession)
    return canonical.target_id_from_key(key)


@pytest.mark.asyncio
async def test_import_stp_writes_predicted_edges_and_skips_measured(
    client, engine, monkeypatch
) -> None:
    c, ids = client
    cid = ids["c1"]  # the single compound we import STP edges for

    # Fake the Stage-3 clients so the un-injected engine path picks them up.
    monkeypatch.setattr(stage3, "ChemblClient", lambda http: _FakeChembl())
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", lambda http: _FakePubchem())
    monkeypatch.setattr(stage3, "UniProtClient", lambda http: _FakeUniProt())

    # import_stp does a LOCAL `from app.integrations.uniprot import UniProtClient`,
    # so patching the module attribute takes effect at call time.
    monkeypatch.setattr("app.integrations.uniprot.UniProtClient", _FakeUniProt)

    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await s.execute(
            text(
                "insert into source_systems(source_name, source_type) values "
                "('ChEMBL', 'api'),('PubChem BioAssay', 'api'),('UniProt', 'api'),"
                "('SwissTargetPrediction', 'api') "
                "on conflict (source_name) do nothing"
            )
        )
        # Only c1 is screened: give it a non-NULL InChIKey, leave c2 NULL.
        await s.execute(
            text("update compounds set inchi_key = 'IKX' where compound_id = :c"),
            {"c": cid},
        )
        await s.commit()

    # Create a guided run on the full plant and walk S1 -> S2 -> S3.
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

    st = await _poll(c, run_id, until="stage_1_awaiting_approval")
    assert st["status"] == "stage_1_awaiting_approval"
    assert (await c.post(f"/analyses/{run_id}/advance")).status_code == 202

    st = await _poll(c, run_id, until="stage_2_awaiting_approval")
    assert st["status"] == "stage_2_awaiting_approval"
    assert (await c.post(f"/analyses/{run_id}/advance")).status_code == 202

    st = await _poll(c, run_id, until="stage_3_awaiting_approval")
    assert st["status"] == "stage_3_awaiting_approval", "guided run must checkpoint at S3"

    p04637 = _target_id_for("P04637")
    p99999 = _target_id_for("P99999")

    # Sanity: the measured chembl edge for (c1, P04637) exists before import.
    async with maker() as s:
        method = (
            await s.execute(
                text(
                    "select prediction_method from compound_targets "
                    "where compound_id = :c and target_id = :t"
                ),
                {"c": cid, "t": p04637},
            )
        ).scalar_one()
        assert method == "chembl_bioactivity"

    # --- STP import: P04637 already measured (skip), P99999 new predicted edge. ---
    imp = await c.post(
        f"/analyses/{run_id}/import-stp-targets",
        json={
            "compound_ids": [str(cid)],
            "rows": [
                {"uniprot": "P04637", "probability": 0.9},
                {"uniprot": "P99999", "probability": 0.8},
            ],
        },
    )
    assert imp.status_code == 200, imp.text
    body = imp.json()
    assert body["imported"] == 1, body
    assert body["skipped_measured"] == 1, body
    assert body["failed"] == [], body

    # DB: a stp_import edge for (c1, P99999) at score 0.8; (c1, P04637) untouched.
    async with maker() as s:
        row = (
            await s.execute(
                text(
                    "select prediction_method, score from compound_targets "
                    "where compound_id = :c and target_id = :t"
                ),
                {"c": cid, "t": p99999},
            )
        ).one()
        assert row.prediction_method == "stp_import"
        assert row.score == pytest.approx(0.8)

        method = (
            await s.execute(
                text(
                    "select prediction_method from compound_targets "
                    "where compound_id = :c and target_id = :t"
                ),
                {"c": cid, "t": p04637},
            )
        ).scalar_one()
        assert method == "chembl_bioactivity", "measured edge must not be overwritten"

    # Run: P99999 now in the Stage-3 set tagged user-added; the edit re-ran from S5 (no S4).
    st = await _poll(c, run_id, until="stage_3_awaiting_approval")
    results = st["stage_results"]
    s3_targets = {t["target_id"]: t for t in results["3"]["targets"]}
    assert p99999 in s3_targets, "imported STP target must join the Stage-3 set"
    assert s3_targets[p99999]["tag"] == "user-added"
    assert "4" not in results, "set edit re-runs from S5; Stage 4 must not be stored"

    # --- Second import REPLACES (not merges) c1's STP edges. ---
    imp2 = await c.post(
        f"/analyses/{run_id}/import-stp-targets",
        json={
            "compound_ids": [str(cid)],
            "rows": [{"uniprot": "P99999", "probability": 0.7}],
        },
    )
    assert imp2.status_code == 200, imp2.text
    assert imp2.json()["imported"] == 1

    async with maker() as s:
        rows = (
            await s.execute(
                text(
                    "select target_id, score from compound_targets "
                    "where compound_id = :c and prediction_method = 'stp_import'"
                ),
                {"c": cid},
            )
        ).all()
        assert len(rows) == 1, "second import replaces the prior stp edges"
        assert str(rows[0].target_id) == p99999
        assert rows[0].score == pytest.approx(0.7)
