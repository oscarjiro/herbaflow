"""Entity-count cap predicate (the single home reused at pre-run entry and in-stage adds).

Caps come from the shared contract (RS.2): compounds <= 2000, targets <= 5000, plants <= 20.
No silent truncation: overflow raises EntityCapExceeded carrying the cap and the current count.
The pass condition is ``current + adding <= cap`` (exactly the cap is allowed).
"""

import pytest

from app import contracts
from app.pipeline.limits import EntityCapExceeded, check_entity_cap


def test_compound_cap_rejects_overflow() -> None:
    with pytest.raises(EntityCapExceeded) as e:
        check_entity_cap("compound", current=1999, adding=2)  # 2001 > 2000
    assert e.value.cap == 2000 and e.value.current == 1999


def test_compound_cap_allows_up_to_limit() -> None:
    check_entity_cap("compound", current=1998, adding=2)  # exactly 2000 -> ok


def test_compound_cap_allows_under_limit() -> None:
    check_entity_cap("compound", current=0, adding=2000)  # exactly 2000 -> ok


def test_target_cap_rejects_overflow() -> None:
    with pytest.raises(EntityCapExceeded) as e:
        check_entity_cap("target", current=4999, adding=2)  # 5001 > 5000
    assert e.value.cap == 5000 and e.value.current == 4999


def test_target_cap_allows_up_to_limit() -> None:
    check_entity_cap("target", current=4998, adding=2)  # exactly 5000 -> ok


def test_plant_cap_rejects_overflow() -> None:
    with pytest.raises(EntityCapExceeded) as e:
        check_entity_cap("plant", current=19, adding=2)  # 21 > 20
    assert e.value.cap == 20 and e.value.current == 19


def test_plant_cap_allows_up_to_limit() -> None:
    check_entity_cap("plant", current=18, adding=2)  # exactly 20 -> ok


def test_plant_cap_sourced_from_contract() -> None:
    # The plant cap must come from contracts.max_plants(), not a re-hardcoded literal.
    with pytest.raises(EntityCapExceeded) as e:
        check_entity_cap("plant", current=contracts.max_plants(), adding=1)
    assert e.value.cap == contracts.max_plants()


def test_compound_cap_sourced_from_contract() -> None:
    assert contracts.max_compounds() == 2000
    with pytest.raises(EntityCapExceeded) as e:
        check_entity_cap("compound", current=contracts.max_compounds(), adding=1)
    assert e.value.cap == contracts.max_compounds()


def test_target_cap_sourced_from_contract() -> None:
    assert contracts.max_targets() == 5000
    with pytest.raises(EntityCapExceeded) as e:
        check_entity_cap("target", current=contracts.max_targets(), adding=1)
    assert e.value.cap == contracts.max_targets()


def test_exception_carries_entity_and_adding() -> None:
    with pytest.raises(EntityCapExceeded) as e:
        check_entity_cap("compound", current=2000, adding=5)
    assert e.value.entity == "compound"
    assert e.value.adding == 5
    assert e.value.cap == 2000
    assert e.value.current == 2000
