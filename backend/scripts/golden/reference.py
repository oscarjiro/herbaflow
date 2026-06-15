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
