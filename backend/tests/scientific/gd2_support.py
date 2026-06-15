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

ONE recorded STRING network (over the 247-gene secondary overlap) serves BOTH runs:
``FakeString`` returns only the recorded edges whose source AND target are both in the called gene
set, so STRING-over-233 == STRING-over-247 filtered to the 233 set.

The four GD-2 fixtures are gitignored (unpublished Hito data); the tests SKIP cleanly when absent.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.integrations.string_db import StringEdge
from app.pipeline.stages import stage3, stage6, stage8
from tests.scientific.conftest import FIXTURES, load_json

GD2_FIXTURES = [
    "gd2_seed.json",
    "gd2_string.json",
    "gd2_hub_ref.json",
    "gd2_snapshot.json",
]


def gd2_fixtures_present() -> bool:
    """True only when all four gitignored GD-2 fixtures exist on this machine."""
    return all((FIXTURES / name).exists() for name in GD2_FIXTURES)


class FakeString:
    """Replay the recorded STRING edges, scoped to the called gene set.

    Returns only edges whose source AND target are both in ``gene_symbols`` — so the single recorded
    247-gene network reproduces the 233-gene network when the 233 set is passed. The server-rendered
    image is absent (None); the image step can never fail the stage.
    """

    def __init__(self, edges: list[dict[str, Any]]) -> None:
        self._edges = edges

    async def network(
        self, gene_symbols: list[str], *, min_confidence: float, network_type: str
    ) -> list[StringEdge]:
        called = set(gene_symbols)
        return [
            StringEdge(e["source"], e["target"], e["confidence"])
            for e in self._edges
            if e["source"] in called and e["target"] in called
        ]

    async def fetch_network_image(
        self, gene_symbols: list[str], *, min_confidence: float, network_type: str
    ) -> bytes | None:
        return None


class FakeGprofiler:
    """Hito supplied no enrichment — g:Profiler is replayed empty (Stage 8 honest-null)."""

    async def profile(
        self,
        *,
        query: list[str],
        background: list[str],
        sources: list[str],
        correction: str,
        user_threshold: float,
        no_iea: bool = False,
    ) -> list[Any]:
        return []


class _RaiseIfCalled:
    """A Stage-3 external client whose construction is forbidden in the offline GD-2 runs.

    The manual entry modes never fetch (create only loads the user-provided ids), so building any
    Stage-3 client would mean the offline contract broke — this guard trips loudly if it ever does.
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("external call in offline GD-2 test")


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
    """Swap STRING + g:Profiler for the recorded fakes; forbid every Stage-3 external client.

    One recorded network backs both runs; g:Profiler is empty. The Stage-3 raise-if-called guards
    PROVE the manual modes run fully offline — no external client is ever constructed.
    """
    edges = load_json("gd2_string.json")
    monkeypatch.setattr(stage6, "StringClient", lambda http: FakeString(edges))
    monkeypatch.setattr(stage8, "GprofilerClient", lambda http: FakeGprofiler())
    monkeypatch.setattr(stage3, "ChemblClient", _RaiseIfCalled)
    monkeypatch.setattr(stage3, "PubChemBioAssayClient", _RaiseIfCalled)
    monkeypatch.setattr(stage3, "UniProtClient", _RaiseIfCalled)
