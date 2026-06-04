"""ETL <-> backend identity parity.

The backend cannot import etl/ (separate venv), so this test pins the backend
canonicalize twin to the exact contract strings that etl/shared/identity.py also
asserts (etl/tests/test_identity.py). If either side drifts, one of these fails.
"""
import uuid

import pytest
from app.services import canonicalize as cz

COMPOUND_NS = uuid.UUID("ea972261-ef25-5420-b17c-317f73ec590e")
TARGET_NS = uuid.UUID("421e4557-e00d-533d-ab26-5f7b761b9483")
COMPOUND_TARGET_NS = uuid.UUID("59a665ef-1743-5e45-98c2-128fe7e345a9")


@pytest.mark.parametrize("ik", ["ABCDEFGHIJKLMN-OPQRSTUVWX-Y", "qwer"])
def test_compound_parity(ik):
    assert cz.compound_canonical_key(ik) == f"inchikey:{ik.upper()}"
    assert cz.make_compound_id(ik) == str(uuid.uuid5(COMPOUND_NS, f"inchikey:{ik.upper()}"))


@pytest.mark.parametrize("acc,expect", [("P04637", "uniprot:P04637"), ("P04637-2", "uniprot:P04637")])
def test_target_parity(acc, expect):
    assert cz.target_canonical_key(acc) == expect
    assert cz.make_target_id(acc) == str(uuid.uuid5(TARGET_NS, expect))


def test_compound_target_parity():
    assert cz.make_compound_target_id("c", "t") == str(uuid.uuid5(COMPOUND_TARGET_NS, "c:t"))
