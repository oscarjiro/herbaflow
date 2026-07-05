"""Unit tests for Stage 2 ADME filter — one test per gate branch, TDD-first.

All tests use SimpleNamespace fakes and injected compute/persist callables, so
no database or RDKit is required at test time.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any

import pytest

from app.pipeline.stages import stage2
from app.services.descriptors import MolDescriptors

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_DEFAULT_PARAMS: dict[str, Any] = {
    "max_mw": 500.0,
    "max_logp": 5.0,
    "max_hbd": 5,
    "max_hba": 10,
    "max_tpsa": 140.0,
    "max_rotatable_bonds": 10,
    "apply_veber": True,
    "np_exception_threshold": 0.0,
    "apply_np_exception": False,
    "max_violations": 1,
    "skip_adme": False,
}


def _params(**overrides: Any) -> dict[str, Any]:
    return {**_DEFAULT_PARAMS, **overrides}


def _seeded(
    *,
    compound_id: uuid.UUID | None = None,
    canonical_name: str = "Test Compound",
    smiles: str = "CCO",
    molecular_weight: float = 46.07,
    logp: float | None = -0.14,
    hbond_donors: int | None = 1,
    hbond_acceptors: int | None = 1,
    tpsa: float | None = 20.23,
    rotatable_bonds: int | None = 0,
    np_likeness_score: float | None = None,
    num_ro5_violations: int = 0,
    is_pains_positive: bool = False,
    source_url: str | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        compound_id=compound_id or uuid.uuid4(),
        canonical_name=canonical_name,
        smiles=smiles,
        molecular_weight=molecular_weight,
        logp=logp,
        hbond_donors=hbond_donors,
        hbond_acceptors=hbond_acceptors,
        tpsa=tpsa,
        rotatable_bonds=rotatable_bonds,
        np_likeness_score=np_likeness_score,
        num_ro5_violations=num_ro5_violations,
        is_pains_positive=is_pains_positive,
        source_url=source_url,
    )


def _manual(
    *,
    compound_id: uuid.UUID | None = None,
    canonical_name: str = "Manual Compound",
    smiles: str = "CCO",
) -> SimpleNamespace:
    """Compound with null descriptors (manual entry / not yet computed)."""
    return SimpleNamespace(
        compound_id=compound_id or uuid.uuid4(),
        canonical_name=canonical_name,
        smiles=smiles,
        molecular_weight=None,
        logp=None,
        hbond_donors=None,
        hbond_acceptors=None,
        tpsa=None,
        rotatable_bonds=None,
        np_likeness_score=None,
        num_ro5_violations=None,
        is_pains_positive=False,
        source_url=None,
    )


def _make_descriptors(**overrides: Any) -> MolDescriptors:
    defaults = dict(
        molecular_weight=46.07,
        logp=-0.14,
        hbond_donors=1,
        hbond_acceptors=1,
        tpsa=20.23,
        rotatable_bonds=0,
        np_likeness_score=None,
        num_ro5_violations=0,
        is_pains_positive=False,
    )
    defaults.update(overrides)
    return MolDescriptors(**defaults)  # type: ignore[arg-type]


async def _fake_compute_none(smiles: str) -> MolDescriptors | None:
    return None


# ---------------------------------------------------------------------------
# Branch 1: skip_adme=True → all pass, badge "unscreened", no compute
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_adme_passes_all_no_compute() -> None:
    compute_called = []

    async def tracking_compute(smiles: str) -> MolDescriptors | None:
        compute_called.append(smiles)
        return None

    c1 = _seeded()
    c2 = _manual()
    result = await stage2.screen(
        [c1, c2],
        _params(skip_adme=True),
        compute=tracking_compute,
    )

    assert result["count"] == 2
    assert len(result["passed"]) == 2
    assert result["filtered"] == []
    assert not compute_called
    for p in result["passed"]:
        assert "unscreened" in p["badges"]
    assert len(result["annotations"]["unscreened"]) == 2


# ---------------------------------------------------------------------------
# Branch 2: seeded compound, 0 violations → passed, descriptor_source "etl"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeded_clean_passes_etl_source() -> None:
    c = _seeded()
    result = await stage2.screen([c], _params(), compute=_fake_compute_none)

    assert result["count"] == 1
    assert result["filtered"] == []
    passed = result["passed"][0]
    assert passed["descriptor_source"] == "etl"
    assert passed["compound_id"] == str(c.compound_id)


@pytest.mark.asyncio
async def test_screened_rows_carry_adme_outcome_fields() -> None:
    c = _seeded()
    c.inchi_key = "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"

    result = await stage2.screen([c], _params(), compute=_fake_compute_none)

    row = result["passed"][0]
    assert row["inchikey"] == "LFQSCWFLJHTTHZ-UHFFFAOYSA-N"
    assert row["lipinski_violations"] == 0
    assert row["lipinski_pass"] is True
    assert row["veber_pass"] is True
    assert row["rule_evaluated"] is True


@pytest.mark.asyncio
async def test_bypass_and_unscreened_rows_mark_rule_not_evaluated() -> None:
    np_bypass = _seeded(
        molecular_weight=800.0,
        logp=8.0,
        hbond_donors=8,
        hbond_acceptors=15,
        tpsa=200.0,
        rotatable_bonds=20,
        np_likeness_score=1.5,
    )
    bypass_result = await stage2.screen(
        [np_bypass],
        _params(apply_np_exception=True, np_exception_threshold=1.0),
        compute=_fake_compute_none,
    )
    bypass_row = bypass_result["passed"][0]
    assert bypass_row["rule_evaluated"] is False
    assert bypass_row["lipinski_violations"] is None
    assert bypass_row["lipinski_pass"] is None
    assert bypass_row["veber_pass"] is None

    unscreened_result = await stage2.screen(
        [_seeded()],
        _params(skip_adme=True),
        compute=_fake_compute_none,
    )
    unscreened_row = unscreened_result["passed"][0]
    assert unscreened_row["rule_evaluated"] is False
    assert unscreened_row["lipinski_violations"] is None
    assert unscreened_row["lipinski_pass"] is None
    assert unscreened_row["veber_pass"] is None


@pytest.mark.asyncio
async def test_could_not_screen_rows_mark_outcomes_as_no_data() -> None:
    result = await stage2.screen([_seeded(logp=None)], _params(), compute=_fake_compute_none)

    row = result["filtered"][0]
    assert row["reason"] == "could not screen"
    assert row["rule_evaluated"] is False
    assert row["lipinski_violations"] is None
    assert row["lipinski_pass"] is None
    assert row["veber_pass"] is None


# ---------------------------------------------------------------------------
# Branch 3: manual/null compound → compute returns descriptors →
#           screened on computed values, descriptor_source "rdkit", persist called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_descriptor_computed_and_persisted() -> None:
    cid = uuid.uuid4()
    c = _manual(compound_id=cid)
    computed = _make_descriptors(molecular_weight=300.0, logp=2.0, num_ro5_violations=0)

    async def fake_compute(smiles: str) -> MolDescriptors | None:
        return computed

    persisted: list[tuple[uuid.UUID, MolDescriptors]] = []

    async def fake_persist(compound_id: uuid.UUID, d: MolDescriptors) -> None:
        persisted.append((compound_id, d))

    result = await stage2.screen([c], _params(), compute=fake_compute, persist=fake_persist)

    assert result["count"] == 1
    passed = result["passed"][0]
    assert passed["descriptor_source"] == "rdkit"
    assert passed["molecular_weight"] == 300.0
    assert len(persisted) == 1
    assert persisted[0][0] == cid


# ---------------------------------------------------------------------------
# Branch 4: null-descriptor + compute returns None → EXCLUDE,
#           reason "could not screen", in annotations["could_not_screen"]
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_null_descriptor_compute_fails_excluded() -> None:
    c = _manual(smiles="")

    result = await stage2.screen([c], _params(), compute=_fake_compute_none)

    assert result["count"] == 0
    assert result["passed"] == []
    assert len(result["filtered"]) == 1
    assert result["filtered"][0]["reason"] == "could not screen"
    assert str(c.compound_id) in result["annotations"]["could_not_screen"]


# ---------------------------------------------------------------------------
# Branch 5a: high NP + apply_np_exception=True → passed with "np_bypass" badge
#            even when it would fail the Lipinski/Veber gates
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_np_bypass_overrides_rules_when_enabled() -> None:
    # Compound violates every Lipinski criterion — would normally be filtered
    c = _seeded(
        molecular_weight=800.0,  # > 500
        logp=8.0,  # > 5
        hbond_donors=8,  # > 5
        hbond_acceptors=15,  # > 10
        tpsa=200.0,  # > 140 (Veber)
        rotatable_bonds=20,  # > 10  (Veber)
        np_likeness_score=1.5,
        num_ro5_violations=4,
    )
    result = await stage2.screen(
        [c],
        _params(apply_np_exception=True, np_exception_threshold=1.0),
        compute=_fake_compute_none,
    )

    assert result["count"] == 1
    passed = result["passed"][0]
    assert "np_bypass" in passed["badges"]
    assert str(c.compound_id) in result["annotations"]["np_bypass"]


# ---------------------------------------------------------------------------
# Branch 5b: same compound but apply_np_exception=False → NOT rescued → filtered
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_np_bypass_disabled_does_not_rescue() -> None:
    c = _seeded(
        molecular_weight=800.0,
        logp=8.0,
        hbond_donors=8,
        hbond_acceptors=15,
        tpsa=200.0,
        rotatable_bonds=20,
        np_likeness_score=1.5,
        num_ro5_violations=4,
    )
    result = await stage2.screen(
        [c],
        _params(apply_np_exception=False, np_exception_threshold=1.0),
        compute=_fake_compute_none,
    )

    assert result["count"] == 0
    assert len(result["filtered"]) == 1


# ---------------------------------------------------------------------------
# Branch 6a: Lipinski budget boundary — exactly max_violations → pass
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lipinski_exactly_at_budget_passes() -> None:
    # max_violations=1; give the compound exactly 1 Lipinski violation (MW > 500)
    c = _seeded(
        molecular_weight=550.0,
        logp=2.0,
        hbond_donors=1,
        hbond_acceptors=2,
        tpsa=60.0,
        rotatable_bonds=3,
        num_ro5_violations=1,
    )
    result = await stage2.screen([c], _params(max_violations=1), compute=_fake_compute_none)

    assert result["count"] == 1


# ---------------------------------------------------------------------------
# Branch 6b: max_violations+1 Lipinski violations → filtered with "N Lipinski violation(s)"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lipinski_over_budget_filtered() -> None:
    # max_violations=1; give 2 Lipinski violations (MW>500 and logP>5)
    c = _seeded(
        molecular_weight=550.0,
        logp=6.0,
        hbond_donors=1,
        hbond_acceptors=2,
        tpsa=60.0,
        rotatable_bonds=3,
        num_ro5_violations=2,
    )
    result = await stage2.screen([c], _params(max_violations=1), compute=_fake_compute_none)

    assert result["count"] == 0
    assert "2 Lipinski violation(s)" in result["filtered"][0]["reason"]


# ---------------------------------------------------------------------------
# Branch 6c: Veber failure NOT counted in Lipinski budget (separate gate)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_veber_failure_reported_as_veber_not_lipinski() -> None:
    # 0 Lipinski violations, but rotatable_bonds > max → Veber fail
    c = _seeded(
        molecular_weight=300.0,
        logp=1.0,
        hbond_donors=1,
        hbond_acceptors=2,
        tpsa=60.0,
        rotatable_bonds=15,  # > 10
        num_ro5_violations=0,
    )
    result = await stage2.screen(
        [c],
        _params(max_violations=1, apply_veber=True, max_rotatable_bonds=10),
        compute=_fake_compute_none,
    )

    assert result["count"] == 0
    reason = result["filtered"][0]["reason"]
    assert "Veber" in reason
    assert "Lipinski" not in reason


# ---------------------------------------------------------------------------
# Branch 7a: apply_veber=True, rotatable_bonds > max → "fails Veber: rotatable bonds"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_veber_rotatable_bonds_filter() -> None:
    c = _seeded(
        molecular_weight=300.0,
        logp=1.0,
        hbond_donors=1,
        hbond_acceptors=2,
        tpsa=60.0,
        rotatable_bonds=15,
        num_ro5_violations=0,
    )
    result = await stage2.screen(
        [c],
        _params(apply_veber=True, max_rotatable_bonds=10, max_tpsa=140.0),
        compute=_fake_compute_none,
    )

    assert result["count"] == 0
    assert "fails Veber: rotatable bonds" in result["filtered"][0]["reason"]


# ---------------------------------------------------------------------------
# Branch 7b: apply_veber=True, tpsa > max → "fails Veber: TPSA"
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_veber_tpsa_filter() -> None:
    c = _seeded(
        molecular_weight=300.0,
        logp=1.0,
        hbond_donors=1,
        hbond_acceptors=2,
        tpsa=200.0,
        rotatable_bonds=3,
        num_ro5_violations=0,
    )
    result = await stage2.screen(
        [c],
        _params(apply_veber=True, max_tpsa=140.0, max_rotatable_bonds=10),
        compute=_fake_compute_none,
    )

    assert result["count"] == 0
    assert "fails Veber: TPSA" in result["filtered"][0]["reason"]


# ---------------------------------------------------------------------------
# Branch 7c: apply_veber=False → Veber ignored even when violations present
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_veber_disabled_is_ignored() -> None:
    c = _seeded(
        molecular_weight=300.0,
        logp=1.0,
        hbond_donors=1,
        hbond_acceptors=2,
        tpsa=200.0,  # would fail Veber
        rotatable_bonds=15,  # would fail Veber
        num_ro5_violations=0,
    )
    result = await stage2.screen([c], _params(apply_veber=False), compute=_fake_compute_none)

    assert result["count"] == 1


# ---------------------------------------------------------------------------
# Branch 8: PAINS — is_pains_positive=True → in passed AND annotations["pains"]
#           with badge "pains"; NEVER removes from passed
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pains_annotated_but_not_filtered() -> None:
    cid = uuid.uuid4()
    c = _seeded(compound_id=cid, is_pains_positive=True, num_ro5_violations=0)
    result = await stage2.screen([c], _params(), compute=_fake_compute_none)

    assert result["count"] == 1
    passed = result["passed"][0]
    assert "pains" in passed["badges"]
    assert str(cid) in result["annotations"]["pains"]
    assert result["filtered"] == []


# ---------------------------------------------------------------------------
# Branch 9: zero-pass — all filtered → count 0, passed []
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_zero_pass_returns_empty_passed() -> None:
    # Compound fails every Lipinski criterion (4 violations > max_violations=1)
    c = _seeded(
        molecular_weight=800.0,
        logp=8.0,
        hbond_donors=8,
        hbond_acceptors=15,
        num_ro5_violations=4,
    )
    result = await stage2.screen([c], _params(max_violations=1), compute=_fake_compute_none)

    assert result["count"] == 0
    assert result["passed"] == []
    assert len(result["filtered"]) == 1


# ---------------------------------------------------------------------------
# NEW: seeded compound with incomplete descriptors → "could not screen"
# (mw present but a Lipinski descriptor is None — live DB has 8 such rows)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_seeded_incomplete_descriptors_could_not_screen() -> None:
    """Seeded compound: mw present, logp NULL → must be EXCLUDED, not silently passed."""
    c = _seeded(logp=None)
    result = await stage2.screen([c], _params(apply_veber=True), compute=_fake_compute_none)

    assert result["count"] == 0, "should NOT silently pass with logp=None"
    assert result["passed"] == []
    assert len(result["filtered"]) == 1
    assert result["filtered"][0]["reason"] == "could not screen"
    assert str(c.compound_id) in result["annotations"]["could_not_screen"]
    assert result["filtered"][0]["descriptor_source"] == "etl"


# ---------------------------------------------------------------------------
# PAINS honesty flag: pains_evaluated is True ONLY where PAINS was computed
# (NP-bypass branch + rule-gate branch), False where it was not (skip_adme +
# could-not-screen). The frontend gates the PAINS cell on this flag.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_np_bypass_row_marks_pains_evaluated() -> None:
    """NP-bypass row: rule not evaluated, but PAINS WAS computed → pains_evaluated True."""
    c = _seeded(
        molecular_weight=800.0,
        logp=8.0,
        hbond_donors=8,
        hbond_acceptors=15,
        tpsa=200.0,
        rotatable_bonds=20,
        np_likeness_score=1.5,
        num_ro5_violations=4,
    )
    result = await stage2.screen(
        [c],
        _params(apply_np_exception=True, np_exception_threshold=1.0),
        compute=_fake_compute_none,
    )

    row = result["passed"][0]
    assert row["rule_evaluated"] is False
    assert row["pains_evaluated"] is True


@pytest.mark.asyncio
async def test_rule_gate_rows_mark_pains_evaluated() -> None:
    """Both a passed and a filtered rule-gate row have pains_evaluated True."""
    passed_c = _seeded()
    passed_result = await stage2.screen([passed_c], _params(), compute=_fake_compute_none)
    assert passed_result["passed"][0]["pains_evaluated"] is True

    filtered_c = _seeded(
        molecular_weight=550.0,
        logp=6.0,
        hbond_donors=1,
        hbond_acceptors=2,
        tpsa=60.0,
        rotatable_bonds=3,
        num_ro5_violations=2,
    )
    filtered_result = await stage2.screen(
        [filtered_c], _params(max_violations=1), compute=_fake_compute_none
    )
    assert filtered_result["filtered"][0]["pains_evaluated"] is True


@pytest.mark.asyncio
async def test_skip_adme_row_marks_pains_not_evaluated() -> None:
    """skip_adme run: PAINS never computed → pains_evaluated False."""
    result = await stage2.screen([_seeded()], _params(skip_adme=True), compute=_fake_compute_none)
    assert result["passed"][0]["pains_evaluated"] is False


@pytest.mark.asyncio
async def test_could_not_screen_row_marks_pains_not_evaluated() -> None:
    """could-not-screen row (seeded, missing Lipinski descriptor): pains_evaluated False."""
    result = await stage2.screen([_seeded(logp=None)], _params(), compute=_fake_compute_none)
    assert result["filtered"][0]["pains_evaluated"] is False


@pytest.mark.asyncio
async def test_seeded_missing_veber_descriptor_only_required_when_veber_on() -> None:
    """tpsa=None, rotatable_bonds=None with valid Lipinski descriptors:
    - apply_veber=False  → screened normally, count == 1 (Veber unused)
    - apply_veber=True   → cannot screen, count == 0
    """
    # apply_veber=False: Veber descriptors not required → should pass Lipinski
    c_off = _seeded(tpsa=None, rotatable_bonds=None)
    result_off = await stage2.screen(
        [c_off], _params(apply_veber=False), compute=_fake_compute_none
    )
    assert (
        result_off["count"] == 1
    ), "Veber descriptors should not be required when apply_veber=False"

    # apply_veber=True: Veber descriptors required → cannot screen
    c_on = _seeded(tpsa=None, rotatable_bonds=None)
    result_on = await stage2.screen([c_on], _params(apply_veber=True), compute=_fake_compute_none)
    assert (
        result_on["count"] == 0
    ), "should not screen when tpsa/rotatable_bonds are None with apply_veber=True"
    assert result_on["filtered"][0]["reason"] == "could not screen"
    assert str(c_on.compound_id) in result_on["annotations"]["could_not_screen"]
