"""RDKit molecular-descriptor computation for ADME screening.

Seeded compounds carry descriptors in DB columns. Manual ``structure_only`` compounds carry
NULL descriptors and must have them computed from canonical SMILES here. This module is the one
canonical home for that computation: a pure ``compute`` plus an async threadpool wrapper so the
RDKit CPU work never blocks the event loop.

The PAINS filter catalog and the (optional) natural-product-likeness model are built once at
import. NP-likeness lives in an RDKit Contrib module that may be absent in some installs; when it
cannot load, every compound gets ``np_likeness_score=None`` and is screened normally downstream.
"""

from __future__ import annotations

import asyncio
import contextlib
import io
from dataclasses import dataclass
from typing import Any

from rdkit import Chem, RDLogger
from rdkit.Chem import Crippen, FilterCatalog, Lipinski
from rdkit.Chem import Descriptors as RDDescriptors

RDLogger.DisableLog("rdApp.*")  # silence parse warnings; bad SMILES surface via a None return

# Canonical Lipinski Rule-of-Five thresholds. These mirror the meaning of the DB
# ``num_ro5_violations`` column (the descriptor's own violation count) — NOT the stage-2 user
# gate (``max_violations``), which lives in the ADME stage.
_RO5_MW = 500.0
_RO5_LOGP = 5.0
_RO5_HBD = 5
_RO5_HBA = 10


def _build_pains_catalog() -> FilterCatalog.FilterCatalog:
    params = FilterCatalog.FilterCatalogParams()
    params.AddCatalog(FilterCatalog.FilterCatalogParams.FilterCatalogs.PAINS)
    return FilterCatalog.FilterCatalog(params)


def _load_np_model() -> Any:
    """Return the natural-product-likeness scorer model, or None if the contrib is absent."""
    try:
        import os
        import sys

        from rdkit.Chem import RDConfig

        npdir = os.path.join(RDConfig.RDContribDir, "NP_Score")
        if npdir not in sys.path:
            sys.path.append(npdir)
        import npscorer  # type: ignore[import-not-found]

        # readNPModel prints progress to stdout; keep test/log output clean.
        with contextlib.redirect_stdout(io.StringIO()):
            return npscorer.readNPModel()
    except Exception:
        return None


_PAINS_CATALOG = _build_pains_catalog()
_NP_MODEL = _load_np_model()


@dataclass(frozen=True)
class MolDescriptors:
    molecular_weight: float
    logp: float
    hbond_donors: int
    hbond_acceptors: int
    tpsa: float
    rotatable_bonds: int
    np_likeness_score: float | None
    num_ro5_violations: int
    is_pains_positive: bool
    descriptor_source: str = "rdkit"


def _count_ro5_violations(mw: float, logp: float, hbd: int, hba: int) -> int:
    return sum(
        (mw > _RO5_MW, logp > _RO5_LOGP, hbd > _RO5_HBD, hba > _RO5_HBA),
    )


def _np_score(mol: Any) -> float | None:
    if _NP_MODEL is None:
        return None
    try:
        import npscorer

        return float(npscorer.scoreMol(mol, _NP_MODEL))
    except Exception:
        return None


def compute(smiles: str) -> MolDescriptors | None:
    """Compute ADME descriptors from a SMILES string, or None if RDKit cannot parse it."""
    mol = Chem.MolFromSmiles(smiles.strip())
    if mol is None:
        return None

    mw = float(RDDescriptors.MolWt(mol))
    logp = float(Crippen.MolLogP(mol))
    hbd = int(Lipinski.NumHDonors(mol))
    hba = int(Lipinski.NumHAcceptors(mol))

    return MolDescriptors(
        molecular_weight=mw,
        logp=logp,
        hbond_donors=hbd,
        hbond_acceptors=hba,
        tpsa=float(RDDescriptors.TPSA(mol)),
        rotatable_bonds=int(Lipinski.NumRotatableBonds(mol)),
        np_likeness_score=_np_score(mol),
        num_ro5_violations=_count_ro5_violations(mw, logp, hbd, hba),
        is_pains_positive=bool(_PAINS_CATALOG.HasMatch(mol)),
    )


async def compute_async(smiles: str) -> MolDescriptors | None:
    """Off-thread ``compute`` so RDKit CPU work never blocks the event loop."""
    return await asyncio.to_thread(compute, smiles)
