from app.pipeline import engine


def test_stage5_registered_and_checkpoint():
    assert 5 in engine.RUNNABLE_STAGES
    assert 5 in engine.NEEDS_APPROVAL
    assert 5 not in engine.STAGE_PARAM_GROUP  # S5 has no params (OV-1)
    assert engine.DEPENDENTS[5] == {6, 8}


def test_stage6_registered_param_bearing():
    assert 6 in engine.RUNNABLE_STAGES
    assert 6 in engine.NEEDS_APPROVAL
    assert engine.STAGE_PARAM_GROUP[6] == "ppi"
    assert engine.DEPENDENTS[6] == {7}


def test_stage7_registered_and_checkpoint():
    assert 7 in engine.RUNNABLE_STAGES
    assert 7 in engine.NEEDS_APPROVAL
    assert engine.STAGE_PARAM_GROUP[7] == "hub_genes"
    assert engine.DEPENDENTS[6] == {7}
    assert engine.DEPENDENTS[7] == set()
