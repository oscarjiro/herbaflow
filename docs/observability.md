# Observability

## Logging standard
The backend logs through one parent logger, `herbaflow`, configured once in
`app/logging_config.py`. Every module uses a child logger
`logging.getLogger("herbaflow.<area>")` (e.g. `herbaflow.analysis`, `herbaflow.pipeline`,
`herbaflow.errors`). Output is a single line to stdout:
`HH:MM:SS LEVEL    herbaflow.<area> | message`. The default level is INFO; the parent does
not propagate to the root logger (no double emit through uvicorn).

## Security-relevant events
The following are logged so the system narrates security-relevant activity:
- run lifecycle: create (with modes + plant/disease), idempotent replay, delete;
- input rejections: validation failures surface as 422 with a per-field reason;
- dependency outages: provider 503s (ChEMBL/STRING) and database-unavailable 503s;
- unhandled errors: logged with stack via the global handler, never leaked to the client.

No secrets, credentials, or full request bodies are logged.

## Startup reaper

On every process start the app runs a one-shot sweep that marks any stranded runs
failed before the server begins accepting requests.  A run is stranded when it is in a
`pending` or `stage_N_running` status at startup; those statuses are only reachable by
an in-flight background task, which cannot exist on a fresh process.  The sweep issues a
single bulk UPDATE, sets the status to `failed` with a user-readable message, and logs
the count at INFO level: `startup reaper: failed N stranded run(s)`.

If the sweep itself fails (for example the database is unreachable), the failure is
logged at WARNING level and startup continues normally.  Stranded runs remain in their
last status until the next successful startup.

Single-instance assumption: this approach is safe only when one server process runs at a
time.  A multi-worker deployment (several processes sharing the same database) would need
a heartbeat column and a `started_at` TTL instead, so a process does not kill runs
belonging to a sibling worker that is still alive.  The current deployment is a single
Render instance, so the startup sweep is safe.
