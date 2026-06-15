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
