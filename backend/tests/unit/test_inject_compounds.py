"""Unit tests for inject-compounds validation.

Tests:
1. Empty compounds list → Pydantic ValidationError (min_length=1)
2. Compounds list exceeding 100 items → Pydantic ValidationError (max_length=100)
3. HTTP boundary: POST /analyses/{id}/inject-compounds with [] → HTTP 422
"""
import pytest
from pydantic import ValidationError
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from app.main import app
from app.schemas.analysis import InjectCompoundsRequest

ANALYSIS_ID = "00000000-0000-0000-0000-000000000043"


# ---------------------------------------------------------------------------
# Test 1: Empty compounds list → ValidationError
# ---------------------------------------------------------------------------


def test_inject_compounds_empty_list_raises_validation_error():
    """InjectCompoundsRequest(compounds=[]) must raise a Pydantic ValidationError.

    The ``compounds`` field has min_length=1, so an empty list is rejected
    before the route handler runs.
    """
    with pytest.raises(ValidationError) as exc_info:
        InjectCompoundsRequest(compounds=[])

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("compounds",) for e in errors)


# ---------------------------------------------------------------------------
# Test 2: Over-limit compounds list → ValidationError
# ---------------------------------------------------------------------------


def test_inject_compounds_over_limit_raises_validation_error():
    """InjectCompoundsRequest with > 100 items must raise a Pydantic ValidationError."""
    with pytest.raises(ValidationError) as exc_info:
        InjectCompoundsRequest(compounds=["CC"] * 101)

    errors = exc_info.value.errors()
    assert any(e["loc"] == ("compounds",) for e in errors)


# ---------------------------------------------------------------------------
# Test 3: HTTP boundary — FastAPI translates Pydantic ValidationError → 422
# ---------------------------------------------------------------------------


def test_inject_compounds_http_empty_list_returns_422():
    """Sending compounds=[] over HTTP must produce a 422 response.

    This confirms FastAPI's request/response boundary: the Pydantic
    ValidationError from InjectCompoundsRequest (min_length=1) is
    automatically converted to HTTP 422 before the route handler runs.
    """
    client = TestClient(app, raise_server_exceptions=False)
    response = client.post(
        f"/analyses/{ANALYSIS_ID}/inject-compounds",
        json={"compounds": []},
    )
    assert response.status_code == 422
