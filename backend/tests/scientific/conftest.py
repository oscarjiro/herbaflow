"""Shared fixtures + API run helper for the golden-dataset scientific suite.

Drives analyses through the REAL API (httpx ASGITransport) in `guided` mode so each
stage is approved explicitly. Verified pipeline facts this helper relies on
(see analysis/pipeline.py, app/routers/analyses.py, app/schemas/analysis.py):

  * POST /analyses (201) returns body with `analysis_id` and `status`. Injecting
    `targets` sets `_input_mode="manual_targets"`, so the pipeline starts at stage 4
    (stages 1-3 are user_provided / not_applicable).
  * Status vocabulary: "pending", "stage_{n}_running", "stage_{n}_awaiting_approval"
    (guided mode only), terminal "complete", and "failed". In guided mode the only
    status containing the terminal word is "complete" itself, so an EXACT match is
    used (the substring `"complet"` would also match the auto-mode "stage_{n}_complete").
  * In guided mode stages 4-7 pause at "stage_{n}_awaiting_approval"; stage 8 is the
    last stage and finalizes directly to "complete" regardless of mode. So a full run
    needs approvals for stages 4,5,6,7 only.
  * POST /analyses/{id}/approve advances to the next stage; it returns 400 if the run
    is not awaiting approval. To avoid re-approving the same awaiting stage during the
    brief window before the background task flips it to "_running", each awaiting stage
    is approved at most once.
"""
import csv
import os
import time

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.main import app

FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")
T2DM_DISEASE_ID = "079e61f1-4104-59c4-9c16-c77fe87dfeae"
EXPECTED_TOTAL_STAGES = 8


def load_gene_fixture(name: str) -> list[str]:
    path = os.path.join(FIXTURES, name)
    with open(path, newline="", encoding="utf-8") as fh:
        return [
            row["gene_symbol"].strip()
            for row in csv.DictReader(fh)
            if row.get("gene_symbol", "").strip()
        ]


@pytest.fixture
def artifacts_dir(request) -> str:
    d = os.path.join(os.path.dirname(__file__), "artifacts", request.node.name)
    os.makedirs(d, exist_ok=True)
    return d


@pytest_asyncio.fixture
async def api_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


def _awaiting_stage(status: str) -> int | None:
    """Return the stage number for a 'stage_{n}_awaiting_approval' status, else None."""
    if status.endswith("_awaiting_approval"):
        try:
            return int(status.split("_")[1])
        except (IndexError, ValueError):
            return None
    return None


async def create_and_run(
    client, *, name, targets, disease_id=None, manual_disease_targets=None,
    mode="guided", poll_timeout_s=600,
) -> dict:
    """Create a manual-targets analysis, drive it to completion, return full stage_results.

    Cleanup is the caller's responsibility (delete the run id) OR rely on the scientific
    suite being opt-in. Returns the parsed `GET /analyses/{id}` body with `_analysis_id`
    appended."""
    body = {
        "name": name,
        "mode": mode,
        "plant_ids": [],
        "disease_id": disease_id,
        "targets": targets,
        "parameters": {},
    }
    if manual_disease_targets is not None:
        body["manual_disease_targets"] = manual_disease_targets
    resp = await client.post("/analyses", json=body)
    assert resp.status_code == 201, resp.text
    analysis_id = resp.json()["analysis_id"]

    approved: set[int] = set()
    deadline = time.time() + poll_timeout_s
    while time.time() < deadline:
        s = (await client.get(f"/analyses/{analysis_id}/status")).json()
        status = s.get("status", "")
        if status == "complete":
            break
        if status == "failed":
            raise AssertionError(f"pipeline failed: {s}")
        stage = _awaiting_stage(status)
        if stage is not None and stage not in approved:
            approved.add(stage)
            r = await client.post(f"/analyses/{analysis_id}/approve")
            assert r.status_code in (200, 400), r.text  # 400 = already advanced; benign
        else:
            time.sleep(2)
    else:
        raise AssertionError(f"pipeline did not finish within {poll_timeout_s}s: last status={status!r}")

    detail = (await client.get(f"/analyses/{analysis_id}")).json()
    detail["_analysis_id"] = analysis_id
    return detail


async def export_all_stages(client, analysis_id: str, out_dir: str) -> None:
    for stage in range(1, 9):
        r = await client.get(f"/analyses/{analysis_id}/export/{stage}?format=csv")
        if r.status_code == 200:
            with open(os.path.join(out_dir, f"stage{stage}.csv"), "wb") as fh:
                fh.write(r.content)
