# etl/tests/test_identity_cas.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.identity import cas_checksum_valid, normalize_cas


def test_valid_cas():
    normalized, is_valid, reason = normalize_cas("50-00-0")  # formaldehyde
    assert normalized == "50-00-0"
    assert is_valid is True
    assert reason == "ok"


def test_invalid_checksum():
    _, is_valid, reason = normalize_cas("50-00-1")
    assert is_valid is False
    assert "checksum" in reason.lower()


def test_unhyphenated_input_normalized():
    normalized, is_valid, _ = normalize_cas("50000")
    assert normalized == "50-00-0"
    assert is_valid is True


def test_empty():
    normalized, is_valid, _ = normalize_cas("")
    assert normalized == ""
    assert is_valid is False


def test_checksum_bool_helper():
    assert cas_checksum_valid("50-00-0") is True
    assert cas_checksum_valid("50-00-1") is False
    assert cas_checksum_valid("not-a-cas") is False
    assert cas_checksum_valid("") is False
