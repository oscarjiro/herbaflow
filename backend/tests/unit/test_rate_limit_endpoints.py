from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
import app.routers.analyses as analyses

ANALYSIS_ID = "00000000-0000-0000-0000-000000000060"


@patch.object(analyses.analysis_repo, "get_run", new_callable=AsyncMock)
def test_export_is_rate_limited(mock_get_run):
    run = MagicMock()
    run.analysis_name = "demo"
    run.stage_results = {"stage_1": {"state": "computed", "compound_ids": ["c1"]}}
    mock_get_run.return_value = run

    limiter = app.state.limiter
    prev = limiter.enabled
    limiter.enabled = True
    limiter.reset()
    try:
        client = TestClient(app, raise_server_exceptions=False)
        # Default export cap is 30/minute -> the 31st call in the window is 429.
        codes = [
            client.get(f"/analyses/{ANALYSIS_ID}/export/1?format=json").status_code
            for _ in range(31)
        ]
        assert 429 in codes
        assert codes.count(200) <= 30
    finally:
        limiter.enabled = prev
        limiter.reset()
