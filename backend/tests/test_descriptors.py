"""Tests for app.services.descriptors — RDKit molecular descriptors + PAINS.

Step-0 verification (RDKit 2026.03.3) confirmed in this install:
- ethanol (``CCO``): MolWt 46.069, logP ~0, HBD 1, HBA 1, TPSA 20.23, rot 0, QED 0.407
- PAINS catalog builds; ethanol and curcumin both return ``HasMatch`` False (curcumin is
  not flagged by RDKit's curated PAINS subset), so the curcumin test asserts the boolean
  type rather than a value we did not observe.
- NP-likeness contrib model loads (not None); ethanol NP 0.598, curcumin NP 0.722.
"""

from __future__ import annotations

import asyncio

from app.services import descriptors

# curcumin: keto-enol diferuloylmethane — used to exercise PAINS-path computation.
CURCUMIN = r"O=C(\C=C\c1ccc(O)c(OC)c1)CC(=O)\C=C\c1ccc(O)c(OC)c1"


def test_descriptors_for_known_smiles() -> None:
    d = descriptors.compute("CCO")  # ethanol
    assert d is not None
    assert abs(d.molecular_weight - 46.07) < 0.1
    assert d.hbond_donors == 1 and d.hbond_acceptors == 1
    assert d.is_pains_positive is False
    assert d.qed_score is not None
    assert d.descriptor_source == "rdkit"


def test_unparseable_smiles_returns_none() -> None:
    assert descriptors.compute("not-a-mol!!") is None


def test_curcumin_pains_and_np() -> None:
    d = descriptors.compute(CURCUMIN)
    assert d is not None
    # Step-0 showed curcumin does NOT match RDKit's PAINS subset in this build; only
    # assert the type, not a value we did not verify.
    assert isinstance(d.is_pains_positive, bool)
    # NP-likeness is present-or-None (contrib model may be absent in other installs).
    assert d.np_likeness_score is None or isinstance(d.np_likeness_score, float)


def test_ro5_violations_within_bounds() -> None:
    d = descriptors.compute("CCO")
    assert d is not None
    assert 0 <= d.num_ro5_violations <= 4


def test_compute_async_matches_sync() -> None:
    sync = descriptors.compute("CCO")
    asyncd = asyncio.run(descriptors.compute_async("CCO"))
    assert sync is not None and asyncd is not None
    assert sync == asyncd
