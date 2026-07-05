"""Stage 2 — ADME drug-likeness filter (Lipinski / Veber / NP-bypass / PAINS).

Gate logic is LOCKED (Methodology Lock §2.5a). Precedence order is strict; do not reorder.

1. skip_adme on? -> PASS, badge "unscreened" (no compute, no filtering)
2. Gather descriptors:
       seeded (molecular_weight not None) -> use DB columns, descriptor_source="etl"
       manual/null (molecular_weight is None) -> compute(smiles); if result:
           descriptor_source="rdkit", persist back; if None -> descriptors unavailable
3. Descriptors unavailable? -> EXCLUDE, reason "could not screen"
4. apply_np_exception AND np_likeness_score is not None
   AND np_likeness_score >= np_exception_threshold
       -> PASS, badge "np_bypass" (overrides BOTH Lipinski and Veber)
5. Rule gate:
       lipinski_violations = count(MW>max_mw, logP>max_logp, HBD>max_hbd, HBA>max_hba)
       lipinski_ok = lipinski_violations <= max_violations
       veber_ok = (not apply_veber) or
                  (rotatable_bonds<=max_rotatable_bonds AND tpsa<=max_tpsa)
       PASS iff (lipinski_ok AND veber_ok); else FILTERED with distinguishing reason
6. PAINS: annotate every screened compound; badge "pains" on passed; NEVER filters.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.compound import CompoundRepository
from app.services import descriptors
from app.services.descriptors import MolDescriptors

logger = logging.getLogger("herbaflow.pipeline")


def _read(obj: Any, name: str, default: Any = None) -> Any:
    """Read an attribute by name, returning ``default`` if absent.

    Using a named helper (rather than inline ``getattr``) satisfies ruff B009
    (no constant-string getattr) while still working for both ORM rows and
    ``SimpleNamespace`` fakes.
    """
    return (
        obj.__dict__.get(name, default) if hasattr(obj, "__dict__") else getattr(obj, name, default)
    )


def _compound_dict(
    obj: Any,
    *,
    descriptor_source: str,
    badges: list[str],
) -> dict[str, Any]:
    """Serialise a compound-like object to a result dict."""
    inchi_key = _read(obj, "inchi_key")
    return {
        "compound_id": str(obj.compound_id),
        "canonical_name": _read(obj, "canonical_name"),
        "smiles": _read(obj, "smiles"),
        "inchi_key": inchi_key,
        "inchikey": inchi_key,
        "descriptor_source": descriptor_source,
        "molecular_weight": _read(obj, "molecular_weight"),
        "logp": _read(obj, "logp"),
        "hbond_donors": _read(obj, "hbond_donors"),
        "hbond_acceptors": _read(obj, "hbond_acceptors"),
        "tpsa": _read(obj, "tpsa"),
        "rotatable_bonds": _read(obj, "rotatable_bonds"),
        "np_likeness_score": _read(obj, "np_likeness_score"),
        "num_ro5_violations": _read(obj, "num_ro5_violations"),
        "is_pains_positive": _read(obj, "is_pains_positive") or False,
        # Honesty flag: True only where PAINS was actually screened (NP-bypass +
        # rule-gate branches). Defaults False so skip_adme / could-not-screen rows,
        # whose is_pains_positive is meaningless, render "-" in the UI.
        "pains_evaluated": False,
        "source_url": _read(obj, "source_url"),
        "badges": badges,
    }


def _mark_pains_evaluated(row: dict[str, Any]) -> None:
    """Record that this row's PAINS value was actually computed (screened)."""
    row["pains_evaluated"] = True


def _blank_rule_outcome(row: dict[str, Any]) -> None:
    row["lipinski_violations"] = None
    row["lipinski_pass"] = None
    row["veber_pass"] = None
    row["rule_evaluated"] = False


def _set_rule_outcome(
    row: dict[str, Any],
    *,
    lipinski_violations: int,
    lipinski_pass: bool,
    veber_pass: bool | None,
) -> None:
    row["lipinski_violations"] = lipinski_violations
    row["lipinski_pass"] = lipinski_pass
    row["veber_pass"] = veber_pass
    row["rule_evaluated"] = True


def _filtered_dict(obj: Any, *, descriptor_source: str, reason: str) -> dict[str, Any]:
    base = _compound_dict(obj, descriptor_source=descriptor_source, badges=[])
    del base["badges"]
    base["reason"] = reason
    return base


def _overlay_descriptors(row: dict[str, Any], d: MolDescriptors, descriptor_source: str) -> None:
    """Overwrite descriptor fields in a result dict with values from a MolDescriptors."""
    row["descriptor_source"] = descriptor_source
    row["molecular_weight"] = d.molecular_weight
    row["logp"] = d.logp
    row["hbond_donors"] = d.hbond_donors
    row["hbond_acceptors"] = d.hbond_acceptors
    row["tpsa"] = d.tpsa
    row["rotatable_bonds"] = d.rotatable_bonds
    row["np_likeness_score"] = d.np_likeness_score
    row["num_ro5_violations"] = d.num_ro5_violations
    row["is_pains_positive"] = d.is_pains_positive


async def screen(
    compounds: list[Any],
    params: dict[str, Any],
    *,
    compute: Callable[[str], Awaitable[MolDescriptors | None]] = descriptors.compute_async,
    persist: Callable[[uuid.UUID, MolDescriptors], Awaitable[None]] | None = None,
    reporter: Any = None,
) -> dict[str, Any]:
    """Screen a list of compound-like objects through the ADME gate.

    Accepts ORM ``Compound`` rows and ``SimpleNamespace`` fakes equally.

    ``persist`` is called only for compounds whose descriptors were computed via RDKit
    (manual/null path). Pass ``None`` to skip persist (unit tests).
    """
    passed: list[dict[str, Any]] = []
    filtered: list[dict[str, Any]] = []
    annotations: dict[str, list[str]] = {
        "pains": [],
        "np_bypass": [],
        "unscreened": [],
        "could_not_screen": [],
    }

    skip_adme: bool = bool(params["skip_adme"])
    apply_np: bool = bool(params["apply_np_exception"])
    np_threshold: float = float(params["np_exception_threshold"])
    apply_veber: bool = bool(params["apply_veber"])
    max_mw: float = float(params["max_mw"])
    max_logp: float = float(params["max_logp"])
    max_hbd: int = int(params["max_hbd"])
    max_hba: int = int(params["max_hba"])
    max_tpsa: float = float(params["max_tpsa"])
    max_rb: int = int(params["max_rotatable_bonds"])
    max_violations: int = int(params["max_violations"])

    total = len(compounds)
    for index, compound in enumerate(compounds):
        if reporter is not None:
            await reporter.update(2, index + 1, total)
        cid = str(compound.compound_id)
        compound_id_uuid: uuid.UUID = compound.compound_id

        # ------------------------------------------------------------------
        # Branch 1: skip_adme
        # ------------------------------------------------------------------
        if skip_adme:
            annotations["unscreened"].append(cid)
            row = _compound_dict(compound, descriptor_source="unscreened", badges=["unscreened"])
            _blank_rule_outcome(row)
            passed.append(row)
            continue

        # ------------------------------------------------------------------
        # Branch 2: gather descriptors
        # ------------------------------------------------------------------
        descriptor_source: str
        mw = _read(compound, "molecular_weight")
        computed_here: bool
        computed_d: MolDescriptors | None

        if mw is not None:
            # Seeded: use DB columns as-is
            descriptor_source = "etl"
            computed_here = False
            computed_d = None

            # Read raw (no or-0 coercion) so missing descriptors surface correctly.
            raw_logp = _read(compound, "logp")
            raw_hbd = _read(compound, "hbond_donors")
            raw_hba = _read(compound, "hbond_acceptors")
            raw_tpsa = _read(compound, "tpsa")
            raw_rb = _read(compound, "rotatable_bonds")

            # Determine which descriptors are required for this screening run.
            # Lipinski descriptors are always required; Veber descriptors only when
            # apply_veber=True.
            lipinski_missing = raw_logp is None or raw_hbd is None or raw_hba is None
            veber_missing = apply_veber and (raw_tpsa is None or raw_rb is None)

            if lipinski_missing or veber_missing:
                # Cannot screen: exclude with reason rather than coercing to 0
                annotations["could_not_screen"].append(cid)
                row = _filtered_dict(compound, descriptor_source="etl", reason="could not screen")
                _blank_rule_outcome(row)
                filtered.append(row)
                continue

            d_mw = float(mw)
            d_logp = float(raw_logp)
            d_hbd = int(raw_hbd)
            d_hba = int(raw_hba)
            # Veber descriptors: use real values when present; 0-fallback is safe when
            # apply_veber=False because d_tpsa/d_rb are only read inside the Veber gate.
            d_tpsa = float(raw_tpsa) if raw_tpsa is not None else 0.0
            d_rb = int(raw_rb) if raw_rb is not None else 0
            d_np: float | None = _read(compound, "np_likeness_score")
            d_pains: bool = bool(_read(compound, "is_pains_positive") or False)
        else:
            # Manual/null: attempt RDKit computation
            smiles: str = _read(compound, "smiles") or ""
            computed_d = await compute(smiles) if smiles else None
            computed_here = True
            if computed_d is not None:
                descriptor_source = "rdkit"
                if persist is not None:
                    await persist(compound_id_uuid, computed_d)
                d_mw = computed_d.molecular_weight
                d_logp = computed_d.logp
                d_hbd = computed_d.hbond_donors
                d_hba = computed_d.hbond_acceptors
                d_tpsa = computed_d.tpsa
                d_rb = computed_d.rotatable_bonds
                d_np = computed_d.np_likeness_score
                d_pains = computed_d.is_pains_positive
            else:
                descriptor_source = "unknown"

        # ------------------------------------------------------------------
        # Branch 3: descriptors unavailable
        # ------------------------------------------------------------------
        if computed_here and computed_d is None:
            annotations["could_not_screen"].append(cid)
            row = _filtered_dict(compound, descriptor_source="unknown", reason="could not screen")
            _blank_rule_outcome(row)
            filtered.append(row)
            continue

        # ------------------------------------------------------------------
        # Branch 4: NP bypass
        # ------------------------------------------------------------------
        if apply_np and d_np is not None and d_np >= np_threshold:
            badges: list[str] = ["np_bypass"]
            if d_pains:
                badges.append("pains")
                annotations["pains"].append(cid)
            annotations["np_bypass"].append(cid)
            row = _compound_dict(compound, descriptor_source=descriptor_source, badges=badges)
            if computed_here and computed_d is not None:
                _overlay_descriptors(row, computed_d, descriptor_source)
            _blank_rule_outcome(row)
            _mark_pains_evaluated(row)
            passed.append(row)
            continue

        # ------------------------------------------------------------------
        # Branch 5: Rule gate (Lipinski + Veber)
        # ------------------------------------------------------------------
        lipo_violations = sum(
            [
                d_mw > max_mw,
                d_logp > max_logp,
                d_hbd > max_hbd,
                d_hba > max_hba,
            ]
        )
        lipinski_ok = lipo_violations <= max_violations

        veber_fail_reasons: list[str] = []
        if apply_veber:
            if d_rb > max_rb:
                veber_fail_reasons.append("fails Veber: rotatable bonds")
            if d_tpsa > max_tpsa:
                veber_fail_reasons.append("fails Veber: TPSA")
        veber_ok = len(veber_fail_reasons) == 0

        # Branch 6: PAINS annotation (every screened compound, regardless of pass/fail)
        if d_pains:
            annotations["pains"].append(cid)

        if lipinski_ok and veber_ok:
            pass_badges: list[str] = []
            if d_pains:
                pass_badges.append("pains")
            pass_row = _compound_dict(
                compound, descriptor_source=descriptor_source, badges=pass_badges
            )
            if computed_here and computed_d is not None:
                _overlay_descriptors(pass_row, computed_d, descriptor_source)
            _set_rule_outcome(
                pass_row,
                lipinski_violations=lipo_violations,
                lipinski_pass=lipinski_ok,
                veber_pass=veber_ok if apply_veber else None,
            )
            _mark_pains_evaluated(pass_row)
            passed.append(pass_row)
        else:
            if not lipinski_ok:
                reason = f"{lipo_violations} Lipinski violation(s)"
            else:
                reason = "; ".join(veber_fail_reasons)
            fail_row = _filtered_dict(compound, descriptor_source=descriptor_source, reason=reason)
            if computed_here and computed_d is not None:
                _overlay_descriptors(fail_row, computed_d, descriptor_source)
            _set_rule_outcome(
                fail_row,
                lipinski_violations=lipo_violations,
                lipinski_pass=lipinski_ok,
                veber_pass=veber_ok if apply_veber else None,
            )
            _mark_pains_evaluated(fail_row)
            filtered.append(fail_row)

    return {
        "passed": passed,
        "filtered": filtered,
        "annotations": annotations,
        "count": len(passed),
        "state": "computed",
    }


async def run(
    session: AsyncSession,
    step1_compounds: list[dict[str, Any]],
    params: dict[str, Any],
    *,
    reporter: Any = None,
) -> dict[str, Any]:
    """Fetch full compound rows and apply the ADME gate.

    ``step1_compounds`` is Stage 1's ``result["compounds"]`` list —
    each element is ``{"compound_id": str, "canonical_name": str | None}``.
    """
    ids = [uuid.UUID(c["compound_id"]) for c in step1_compounds]
    repo = CompoundRepository(session)
    rows = await repo.get_many(ids)

    async def _persist(compound_id: uuid.UUID, d: MolDescriptors) -> None:
        await repo.update_descriptors(compound_id, d)

    result = await screen(rows, params, persist=_persist, reporter=reporter)

    logger.info(
        "stage 2: %d passed, %d filtered, %d unscreened",
        result["count"],
        len(result["filtered"]),
        len(result["annotations"]["unscreened"]),
    )
    return result
