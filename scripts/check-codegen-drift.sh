#!/usr/bin/env bash
# Fail if regenerating the OpenAPI schema or the TS client produces a diff vs committed.
set -euo pipefail
( cd backend && uv run python scripts/dump_openapi.py )
( cd frontend && pnpm gen:api )
if ! git diff --quiet -- backend/openapi.json frontend/src/api; then
  echo "ERROR: generated artifacts are stale. Run the generators and commit."
  git --no-pager diff --stat -- backend/openapi.json frontend/src/api
  exit 1
fi
echo "codegen up to date."
