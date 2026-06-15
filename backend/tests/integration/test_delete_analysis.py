# `client` yields (httpx AsyncClient, seeded ids). No `selection_payload` fixture — build inline.


def _body(ids) -> dict:
    return {
        "plant_ids": [str(ids["plant_full"])],
        "disease_id": str(ids["disease"]),
        "mode": "guided",
    }


async def test_delete_removes_run(client) -> None:
    c, ids = client
    created = await c.post("/analyses", json=_body(ids))
    rid = created.json()["analysis_id"]
    resp = await c.delete(f"/analyses/{rid}")
    assert resp.status_code == 204
    assert (await c.get(f"/analyses/{rid}")).status_code == 404


async def test_delete_missing_run_404(client) -> None:
    c, _ = client
    resp = await c.delete("/analyses/00000000-0000-0000-0000-000000000000")
    assert resp.status_code == 404
    assert resp.headers["content-type"] == "application/problem+json"


async def test_execute_run_refetch_stops_midway_on_real_db(session) -> None:
    """On real Postgres: when the per-stage refetch reports the run gone, the pipeline halts.

    Why a spy and not an in-runner delete: the cooperative stop is detected by the per-stage
    re-read at the TOP of the next stage. Actually deleting the row from the *same* session mid
    stage would make that stage's trailing writes target a deleted row (StaleDataError); doing it
    from a *second* session deadlocks in-process (the pipeline holds the row lock from set_status,
    so a concurrent DELETE blocks on the single event-loop thread). True cross-connection
    concurrency is proven by the live proof. Here we wrap the real repo so get() reports the run
    gone exactly at the stage-2 boundary, while every WRITE still hits the real (existing) row on
    real Postgres, so the per-stage commit + refetch-stop path is exercised end-to-end with no
    crash.
    """
    import uuid as _uuid

    from app.pipeline import engine
    from app.repositories.analysis import AnalysisRepository

    repo = AnalysisRepository(session)
    run = await repo.create(
        analysis_name=None, disease_id=None, plant_ids=[], mode="auto", idempotency_key=None
    )
    await session.commit()
    rid = run.analysis_id

    class _GoneAt2:
        """Delegates everything to the real repo, but get() returns None after 2 calls."""

        def __init__(self, inner: AnalysisRepository) -> None:
            self.inner = inner
            self.calls = 0

        async def get(self, analysis_id):
            self.calls += 1
            return None if self.calls > 2 else await self.inner.get(analysis_id)

        def __getattr__(self, name):  # commit/set_status/set_stage_result/... -> real repo
            return getattr(self.inner, name)

    spy = _GoneAt2(repo)
    ran: list[int] = []

    async def runner(r):
        ran.append(1)
        return {
            "count": 1,
            "compounds": [{"compound_id": str(_uuid.uuid4()), "canonical_name": "c"}],
        }

    runners = {s: runner for s in engine.RUNNABLE_STAGES}
    # pre-loop get(1) + stage-1 top get(2) see the run; stage-2 top get(3) -> None -> stop.
    await engine.execute_run(spy, rid, runners, start_stage=1)

    assert ran == [1]  # stage 1 ran on real Postgres; refetch said gone at stage 2 -> stop
    assert spy.calls == 3
