#!/usr/bin/env python
"""Fail if regenerating the OpenAPI schema or TS client differs from what's committed.

Cross-platform (no shell): the single drift gate, used by both pre-commit and CI.
Resolves each tool via PATH so it works the same on Windows and Linux.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GENERATED = ["backend/openapi.json", "frontend/src/api"]


def tool(name: str) -> str:
    path = shutil.which(name)
    if path is None:
        sys.exit(f"required tool not found on PATH: {name}")
    return path


def main() -> int:
    subprocess.run(
        [tool("uv"), "run", "python", "scripts/dump_openapi.py"],
        cwd=ROOT / "backend",
        check=True,
    )
    subprocess.run([tool("pnpm"), "gen:api"], cwd=ROOT / "frontend", check=True)

    drifted = subprocess.run(
        [tool("git"), "diff", "--quiet", "--", *GENERATED], cwd=ROOT
    ).returncode
    if drifted:
        print("ERROR: generated artifacts are stale. Run the generators and commit.")
        subprocess.run(
            [tool("git"), "--no-pager", "diff", "--stat", "--", *GENERATED], cwd=ROOT
        )
        return 1
    print("codegen up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
