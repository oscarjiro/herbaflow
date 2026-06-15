from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app, raise_server_exceptions=False)


def _assert_headers(resp):
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]


def test_security_headers_on_success_response():
    _assert_headers(client.get("/openapi.json"))


def test_security_headers_on_error_response():
    _assert_headers(client.get("/no-such-route"))  # 404 still carries the headers
