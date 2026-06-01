import inspect

from analysis.stages import stage7_hub_genes


def test_stage7_run_has_no_target_rankings_write():
    src = inspect.getsource(stage7_hub_genes.run)
    assert "TargetRanking" not in src, "stage7 must not write the target_rankings table"
    assert "session.add" not in src, "stage7 must not persist rows"
    assert "session.commit" not in src
