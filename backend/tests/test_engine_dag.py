from app.pipeline import engine


def test_downstream_closure_from_stage_1() -> None:
    assert engine.downstream_closure(1) == {2, 3, 5, 6, 7, 8}


def test_downstream_closure_from_stage_2() -> None:
    assert engine.downstream_closure(2) == {3, 5, 6, 7, 8}


def test_downstream_closure_from_stage_3() -> None:
    assert engine.downstream_closure(3) == {5, 6, 7, 8}


def test_downstream_closure_from_stage_4() -> None:
    assert engine.downstream_closure(4) == {5, 6, 7, 8}


def test_downstream_closure_from_stage_5() -> None:
    assert engine.downstream_closure(5) == {6, 7, 8}


def test_leaves_have_no_dependents() -> None:
    assert engine.downstream_closure(7) == set()
    assert engine.downstream_closure(8) == set()


def test_stage_4_is_sibling_not_downstream_of_1_2_3() -> None:
    # S4 (disease side) is a parallel branch: it is never downstream of the
    # plant-side stages, and S3 is never downstream of S4.
    assert 4 not in engine.downstream_closure(1)
    assert 4 not in engine.downstream_closure(2)
    assert 4 not in engine.downstream_closure(3)
    assert 3 not in engine.downstream_closure(4)
