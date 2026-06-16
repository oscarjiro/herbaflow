"""Shared support for the GD-2 Hito pancreatic-cancer golden regression (OFFLINE, Level-A).

GD-2 is an input-controlled validation of Herbaflow's MCC hub ranker against the pancreatic-cancer
thesis result. Both regression runs feed pre-resolved Target ids straight into the pipeline via the
manual entry modes, so Stages 1-4 do no work beyond loading the user-provided ids:

- plant side ``manual_targets`` (``manual_target_ids``) and disease side ``manual_disease_targets``
  (``manual_disease_target_ids``, NO ``disease_id``). Create only VERIFIES the ids exist and loads
  them via ``get_many`` — no external call, no organism check — so seeding plain Target rows
  (``target_id``/``canonical_key``/``gene_symbol``; accession null) is sufficient.
- Stage 5 overlaps the two id sets, Stage 6 calls STRING over the overlap gene set, Stage 7 ranks by
  MCC, Stage 8 calls g:Profiler over the overlap. Hito supplied no enrichment, so g:Profiler is
  replayed EMPTY (the run still completes; Stage 8 is honest-null).

ONE recorded STRING network (over the 247-gene secondary overlap) serves BOTH runs: the shared
``ReplayString`` returns only the recorded edges whose source AND target are both in the called gene
set, so STRING-over-233 == STRING-over-247 filtered to the 233 set.

The four GD-2 fixtures are gitignored (unpublished Hito data); the tests SKIP cleanly when absent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.pipeline.stages import stage6, stage8
from tests.scientific.conftest import FIXTURES, load_json
from tests.scientific.replay import ReplayGprofiler, ReplayString, forbid_stage3_clients

GD2_FIXTURES = [
    "gd2_seed.json",
    "gd2_string.json",
    "gd2_hub_ref.json",
    "gd2_snapshot.json",
]


def gd2_fixtures_present() -> bool:
    """True only when all four gitignored GD-2 fixtures exist on this machine."""
    return all((FIXTURES / name).exists() for name in GD2_FIXTURES)


def gd2_string_client() -> ReplayString:
    """Replay the recorded 247-gene STRING network; the filter scopes it to the called set."""
    return ReplayString(load_json("gd2_string.json"))


def gd2_gprofiler_client() -> ReplayGprofiler:
    """Hito supplied no enrichment — g:Profiler is replayed empty (Stage 8 honest-null)."""
    return ReplayGprofiler([])


async def seed_gd2(engine: AsyncEngine) -> dict[str, Any]:
    """Insert the 1695 canonical Target rows and return the seed dict.

    NO source_systems, NO compound_targets, NO disease_targets — the manual modes feed pre-resolved
    target ids and verify existence only. ``target_id`` is a deterministic ``uuid5`` of the gene
    symbol. All SQL is parameterized (multi-row insert), mirroring the integration seed style.
    """
    seed = load_json("gd2_seed.json")
    maker = async_sessionmaker(engine, expire_on_commit=False)
    async with maker() as s:
        await s.execute(
            text(
                "insert into targets(target_id, canonical_key, gene_symbol) "
                "values (:target_id, :canonical_key, :gene_symbol)"
            ),
            [
                {
                    "target_id": t["target_id"],
                    "canonical_key": t["canonical_key"],
                    "gene_symbol": t.get("gene_symbol"),
                }
                for t in seed["targets"]
            ],
        )
        await s.commit()
    return seed


def patch_gd2(monkeypatch: Any) -> None:
    """Swap STRING + g:Profiler for the replay doubles; forbid every Stage-3 external client.

    One recorded network backs both runs; g:Profiler is empty. The Stage-3 raise-if-called guards
    PROVE the manual modes run fully offline — no external client is ever constructed.
    """
    monkeypatch.setattr(stage6, "StringClient", lambda http: gd2_string_client())
    monkeypatch.setattr(stage8, "GprofilerClient", lambda http: gd2_gprofiler_client())
    forbid_stage3_clients(monkeypatch)
