# backend/tests/integration/test_sql_injection.py
#
# Proves injection inputs are safe on both entry surfaces:
#   1. POST /analyses types plant_ids/disease_id as UUIDs, so an injection string is rejected at
#      the validation boundary (422) and never reaches SQL.
#   2. POST /compounds/validate free-text goes through resolve_compounds, which canonicalizes and
#      does parameterized DB lookups; junk resolves to a `failed` entry with a reason, never a 500
#      and never executed as SQL.
#
# The integration `client` fixture (conftest.py) yields a TUPLE: (httpx AsyncClient, seeded ids),
# with get_session bound to the testcontainers Postgres. asyncio_mode="auto", so bare
# `async def test_...` needs no marker. The httpx_mock marker below registers NO response and keeps
# the default `assert_all_requests_were_expected=True`: any outbound HTTP request the resolver tried
# to make on these inputs would raise, proving the junk is never networked.

import pytest

INJECTION = [
    "'; DROP TABLE analysis_runs; --",
    "1 OR 1=1",
    "<script>alert(1)</script>",
    "robert'); DROP TABLE plants;--",
]


@pytest.fixture
def non_mocked_hosts() -> list[str]:
    # Let the test's own ASGITransport calls (host "test") through; any other host is intercepted
    # by httpx_mock and, since no response is registered, would raise.
    return ["test"]


@pytest.mark.integration
async def test_injection_in_typed_uuid_fields_is_rejected_422(client) -> None:
    c, _ = client
    for evil in INJECTION:
        resp = await c.post("/analyses", json={"plant_ids": [evil], "disease_id": evil})
        # The UUID type boundary rejects the input before any SQL runs.
        assert resp.status_code == 422, (evil, resp.status_code, resp.text)


@pytest.mark.integration
@pytest.mark.httpx_mock(assert_all_responses_were_requested=False)
async def test_injection_in_free_text_inputs_is_opaque(client) -> None:
    c, _ = client
    for evil in INJECTION:
        resp = await c.post("/compounds/validate", json={"inputs": [{"value": evil}]})
        assert resp.status_code == 200, (evil, resp.status_code, resp.text)  # never a 500
        body = resp.json()
        assert body["resolved"] == [], (evil, body)
        assert len(body["failed"]) == 1, (evil, body)
        # Honest reason, not a silent drop (no-silent-drops contract).
        assert body["failed"][0].get("reason"), (evil, body)
        assert body["failed"][0]["value"] == evil, (evil, body)
