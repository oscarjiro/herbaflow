from app.pipeline import engine


def test_stage5_registered_and_checkpoint():
    assert 5 in engine.RUNNABLE_STAGES
    assert 5 in engine.NEEDS_APPROVAL
    assert 5 not in engine.STAGE_PARAM_GROUP  # S5 has no params (OV-1)
    assert engine.DEPENDENTS[5] == {6, 8}
