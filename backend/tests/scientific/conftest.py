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
import asyncio
import csv
import os
import socket
import threading
import time

import pytest
import pytest_asyncio
import uvicorn
from app.main import app
from httpx import AsyncClient, Limits

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


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@pytest.fixture(scope="session")
def live_server_url():
    """Run the real app under uvicorn in a background thread, driven over TCP.

    Why a real server (not httpx ASGITransport): the golden pipeline advances via
    POST /approve, which holds a FOR UPDATE on the run row in its request session and
    schedules run_stage as a background task that UPDATEs the same row. Under ASGITransport
    the request and its background task share the test's event loop, so the background UPDATE
    deadlocks against the request's still-held FOR UPDATE (statement timeout). A real server
    runs requests and background tasks with production lifecycle semantics — the request
    (and its lock) is released before the background task runs — so the approve loop works.
    """
    port = _free_port()
    config = uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    deadline = time.time() + 30
    while time.time() < deadline:
        if getattr(server, "started", False):
            break
        time.sleep(0.1)
    else:
        raise RuntimeError("uvicorn test server did not start within 30s")
    yield f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(timeout=10)


@pytest_asyncio.fixture
async def api_client(live_server_url):
    # max_keepalive_connections=0: close each connection after its response so nothing
    # lingers to be torn down after the event loop closes (avoids a Windows-proactor
    # "Event loop is closed" RuntimeError during fixture teardown).
    async with AsyncClient(
        base_url=live_server_url, timeout=120.0,
        limits=Limits(max_keepalive_connections=0),
    ) as client:
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
    mode="auto", poll_timeout_s=600,
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
        # Lenient injection: STP gene symbols are normalized offline (HGNC), no per-symbol
        # UniProt round-trip. Keeps the golden run deterministic and UniProt-independent.
        "skip_validation": True,
        "parameters": {},
    }
    if manual_disease_targets is not None:
        body["manual_disease_targets"] = manual_disease_targets
    resp = await client.post("/analyses", json=body)
    assert resp.status_code == 201, resp.text
    analysis_id = resp.json()["analysis_id"]

    # NOTE: this runs on the same event loop as the ASGI app under httpx ASGITransport.
    # Never block the loop (no time.sleep) — the approve handler holds a FOR UPDATE on the
    # run row via its request session, and the scheduled run_stage background task + session
    # teardown only progress when the loop is free. Blocking would stall lock release and
    # deadlock the next approve's FOR UPDATE. Use await asyncio.sleep, and settle briefly
    # after each approve so the prior request's transaction releases before the next poll.
    approved: set[int] = set()
    deadline = time.time() + poll_timeout_s
    status = ""
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
            await asyncio.sleep(1.0)
        else:
            await asyncio.sleep(2)
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
