import pytest
from analysis.models import AdmeParams, CompoundRecord

from tests.scientific.data_prep.select_curcuma_compounds import screen_compounds

pytestmark = pytest.mark.scientific


def _rec(cid, mw, logp, hbd, hba, tpsa=50.0, rot=3, npl=0.0, smiles="CCO"):
    return CompoundRecord(
        compound_id=cid, canonical_name=cid, smiles=smiles, chembl_id=None,
        pubchem_cid=None, molecular_weight=mw, logp=logp, hbond_donors=hbd,
        hbond_acceptors=hba, tpsa=tpsa, rotatable_bonds=rot, np_likeness_score=npl,
    )


def test_screen_keeps_druglike_and_np_exceptions_drops_failures():
    records = [
        _rec("ok", 300, 2.0, 2, 4),                 # passes Lipinski+Veber
        _rec("toobig", 900, 9.0, 9, 20),            # fails, low NP-likeness → dropped
        _rec("np", 900, 9.0, 9, 20, npl=0.8),       # fails RO5 but NP-exception → kept
    ]
    kept = screen_compounds(records, AdmeParams())
    ids = {r.compound_id for r in kept}
    assert ids == {"ok", "np"}


def test_screen_returns_smiles_for_kept():
    kept = screen_compounds([_rec("ok", 300, 2.0, 2, 4, smiles="C1=CC=CC=C1")], AdmeParams())
    assert kept[0].smiles == "C1=CC=CC=C1"
