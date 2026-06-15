from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

_FIX = Path(__file__).resolve().parents[2] / "tests" / "scientific" / "fixtures"


@dataclass(frozen=True)
class ReferenceSet:
    gene_set: set[str]
    universe: int
    _papers: dict[str, list[str]]

    def papers_for(self, gene: str) -> list[str]:
        return self._papers.get(gene, [])


def load_gd1() -> ReferenceSet:
    data = json.loads((_FIX / "gd1_reference_genes.json").read_text(encoding="utf-8"))
    genes = data["genes"]
    return ReferenceSet(
        set(genes),
        int(data["universe"]),
        {g: meta.get("papers", []) for g, meta in genes.items()},
    )


@dataclass(frozen=True)
class Gd2HubMetric:
    """The reference study's reported figures for one top-10 hub gene."""

    rank: int
    gene_symbol: str
    degree: float
    betweenness: float
    closeness: float
    eigenvector: float
    score: float


@dataclass(frozen=True)
class Gd2Reference:
    """The reference (Hito) pancreatic-cancer hub ranking and shared-target set.

    ``hito_top10`` is the reference's top-10 gene symbols ordered best-first (ascending rank).
    ``overlap_233`` is the reference study's reported 233-gene shared-target set. ``metrics`` maps
    each top-10 gene symbol to its reported rank, four centralities, and composite score, for the
    hub comparison table. Pure: this reads JSON only and computes nothing.
    """

    hito_top10: tuple[str, ...]
    overlap_233: frozenset[str]
    metrics: dict[str, Gd2HubMetric]

    def rank_of(self, gene: str) -> int | None:
        m = self.metrics.get(gene)
        return m.rank if m is not None else None

    def score_of(self, gene: str) -> float | None:
        m = self.metrics.get(gene)
        return m.score if m is not None else None


def load_gd2() -> Gd2Reference:
    data = json.loads((_FIX / "gd2_hub_ref.json").read_text(encoding="utf-8"))
    rows = sorted(data["hub_genes"], key=lambda r: r["rank"])
    metrics = {
        r["gene_symbol"]: Gd2HubMetric(
            rank=int(r["rank"]),
            gene_symbol=r["gene_symbol"],
            degree=float(r["degree"]),
            betweenness=float(r["betweenness"]),
            closeness=float(r["closeness"]),
            eigenvector=float(r["eigenvector"]),
            score=float(r["score"]),
        )
        for r in rows
    }
    return Gd2Reference(
        hito_top10=tuple(r["gene_symbol"] for r in rows),
        overlap_233=frozenset(data["overlap_233"]),
        metrics=metrics,
    )
