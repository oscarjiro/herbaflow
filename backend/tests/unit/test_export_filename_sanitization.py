from unittest.mock import AsyncMock, MagicMock, patch

import app.routers.analyses as analyses
from app.main import app
from fastapi.testclient import TestClient

ANALYSIS_ID = "00000000-0000-0000-0000-000000000051"
NASTY = 'evil\r\nSet-Cookie: x"; name=/etc/passwd'


def _run_with_name(name: str):
    run = MagicMock()
    run.analysis_name = name
    run.stage_results = {
        "stage_1": {"state": "computed", "compound_ids": ["c1", "c2"]},
    }
    return run


def _assert_clean_header(value: str):
    for bad in ["\r", "\n", '"', "/", "\\", ":"]:
        assert bad not in value, f"unsafe char {bad!r} in header: {value!r}"


@patch.object(analyses.analysis_repo, "get_run", new_callable=AsyncMock)
def test_json_export_filename_sanitized(mock_get_run):
    mock_get_run.return_value = _run_with_name(NASTY)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/analyses/{ANALYSIS_ID}/export/1?format=json")
    assert r.status_code == 200
    _assert_clean_header(r.headers["content-disposition"])


@patch.object(analyses.analysis_repo, "get_run", new_callable=AsyncMock)
def test_csv_export_filename_sanitized(mock_get_run):
    mock_get_run.return_value = _run_with_name(NASTY)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.get(f"/analyses/{ANALYSIS_ID}/export/1?format=csv")
    assert r.status_code == 200
    _assert_clean_header(r.headers["content-disposition"])
