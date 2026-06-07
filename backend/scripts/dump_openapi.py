"""Write the FastAPI OpenAPI schema to backend/openapi.json (codegen input)."""

import json
import sys
from pathlib import Path


def main() -> None:
    backend_root = Path(__file__).resolve().parents[1]
    # Run as a script (`python scripts/dump_openapi.py`) puts scripts/ on sys.path,
    # not the backend root, so make `app` importable before importing it.
    sys.path.insert(0, str(backend_root))
    from app.main import app

    (backend_root / "openapi.json").write_text(json.dumps(app.openapi(), indent=2) + "\n")


if __name__ == "__main__":
    main()
