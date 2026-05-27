from analysis.models import AdmeParams, CompoundRecord, PipelineConfig
from app.models.analysis import AnalysisRun
from sqlmodel.ext.asyncio.session import AsyncSession
from app.repositories import compound_repo


# Core Lipinski properties that must exist for a compound to be evaluable.
# If every one of these is None the compound was never enriched from PubChem
# and cannot be shown to satisfy drug-likeness rules — it must fail.
_CORE_PROPS = ("molecular_weight", "logp", "hbond_donors", "hbond_acceptors")


def filter_compounds(
    compounds: list[CompoundRecord], params: AdmeParams
) -> dict:
    passed, failed, np_exceptions = [], [], []

    for c in compounds:
        # Bypass: user_provided compounds skip ADME when apply_adme_to_manual=False.
        if not params.apply_adme_to_manual and getattr(c, "source", "plant") == "user_provided":
            passed.append(c)
            continue

        # All core properties absent — insufficient data, cannot pass.
        if all(getattr(c, p) is None for p in _CORE_PROPS):
            # No drug-likeness data available — cannot determine NP exception eligibility either.
            failed.append(c)
            continue

        violations = []

        if c.molecular_weight is not None and c.molecular_weight > params.max_mw:
            violations.append("mw")
        if c.logp is not None and c.logp > params.max_logp:
            violations.append("logp")
        if c.hbond_donors is not None and c.hbond_donors > params.max_hbd:
            violations.append("hbd")
        if c.hbond_acceptors is not None and c.hbond_acceptors > params.max_hba:
            violations.append("hba")

        if params.apply_veber:
            if c.tpsa is not None and c.tpsa > params.max_tpsa:
                violations.append("tpsa")
            if c.rotatable_bonds is not None and c.rotatable_bonds > params.max_rotatable_bonds:
                violations.append("rotatable_bonds")

        if not violations:
            passed.append(c)
        elif (
            c.np_likeness_score is not None
            and c.np_likeness_score >= params.np_exception_threshold
        ):
            np_exceptions.append(c)
        else:
            failed.append(c)

    return {
        "passed": passed,
        "failed": failed,
        "np_exceptions": np_exceptions,
        "passed_count": len(passed),
        "failed_count": len(failed),
        "np_exception_count": len(np_exceptions),
    }


async def run(run: AnalysisRun, config: PipelineConfig, session: AsyncSession) -> dict:
    stage1 = (run.stage_results or {}).get("stage_1", {})
    compound_ids = stage1.get("compound_ids", [])

    if not compound_ids:
        return {"passed": 0, "failed": 0, "np_exceptions": 0,
                "passed_compound_ids": [], "np_exception_compound_ids": [],
                "all_active_compound_ids": [], "compounds": []}

    # IDs stored by inject_compounds so the ADME bypass can identify manual compounds.
    manual_ids: set[str] = set((run.parameters or {}).get("manual_compound_ids", []))

    fetched = await compound_repo.get_compounds_by_ids(session, compound_ids)
    db_compounds = []
    for c in fetched:
        db_compounds.append(CompoundRecord(
                compound_id=c.compound_id,
                canonical_name=c.canonical_name,
                smiles=c.smiles,
                chembl_id=c.chembl_id,
                pubchem_cid=c.pubchem_cid,
                molecular_weight=c.molecular_weight,
                logp=c.logp,
                hbond_donors=c.hbond_donors,
                hbond_acceptors=c.hbond_acceptors,
                tpsa=c.tpsa,
                rotatable_bonds=c.rotatable_bonds,
                np_likeness_score=c.np_likeness_score,
                is_pains_positive=c.is_pains_positive,
                num_ro5_violations=c.num_ro5_violations,
                source="user_provided" if str(c.compound_id) in manual_ids else "plant",
            ))

    result = filter_compounds(db_compounds, config.adme)

    # Build plant_ids lookup from Stage 1 enriched compounds
    stage1_compounds = stage1.get("compounds", [])
    plant_ids_map = {c["compound_id"]: c.get("plant_ids", []) for c in stage1_compounds}

    passed_set = {str(c.compound_id) for c in result["passed"]}
    np_set = {str(c.compound_id) for c in result["np_exceptions"]}
    enriched = [
        {
            "compound_id": str(c.compound_id),
            "canonical_name": c.canonical_name or str(c.compound_id),
            "plant_ids": plant_ids_map.get(str(c.compound_id), []),
            "adme_pass": str(c.compound_id) in passed_set,
            "is_np_exception": str(c.compound_id) in np_set,
            "is_pains_positive": c.is_pains_positive,
            # ADME property values for frontend display
            "molecular_weight": c.molecular_weight,
            "logp": c.logp,
            "tpsa": c.tpsa,
            "hbond_donors": c.hbond_donors,
            "hbond_acceptors": c.hbond_acceptors,
            "np_likeness_score": c.np_likeness_score,
            "rotatable_bonds": c.rotatable_bonds,
        }
        for c in result["passed"] + result["np_exceptions"] + result["failed"]
    ]

    return {
        # Frontend display keys
        "passed": result["passed_count"],
        "failed": result["failed_count"],
        "np_exceptions": result["np_exception_count"],
        # Pipeline chain compatibility (Stage 3 reads these)
        # str() cast ensures UUID objects from the ORM are serialized as strings,
        # preventing type mismatches when Stage 3 intersects these IDs with its own sets.
        "passed_compound_ids": [str(c.compound_id) for c in result["passed"]],
        "np_exception_compound_ids": [str(c.compound_id) for c in result["np_exceptions"]],
        "all_active_compound_ids": [
            str(c.compound_id)
            for c in result["passed"] + result["np_exceptions"]
        ],
        "compounds": enriched,
    }
