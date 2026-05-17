"""
Disease ETL pipeline orchestrator.

Runs stages normalize -> map_ontology -> build_canonical -> validate -> export
using settings from diseases/settings.yml.

Usage:
    python main.py [--start N] [--end N] [--dry-run]
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging

STAGE_KEYS = [
    "normalize",
    "map_ontology",
    "build_canonical",
    "validate",
    "export",
]
NUM_STAGES = len(STAGE_KEYS)

STAGE_SCRIPTS = {
    "normalize": "diseases/01_normalize/run.py",
    "map_ontology": "diseases/02_map_ontology/run.py",
    "build_canonical": "diseases/03_build_canonical/run.py",
    "validate": "diseases/04_validate/run.py",
    "export": "diseases/05_export/run.py",
}


def build_cmd(step_key: str, cfg: dict) -> list[str]:
    script = ETL_ROOT / STAGE_SCRIPTS[step_key]
    return [sys.executable, str(script)]


def main() -> int:
    cfg = load_settings("diseases")
    log = setup_logging("diseases.main", cfg)

    parser = argparse.ArgumentParser(description="Herbaflow Diseases ETL Pipeline")
    parser.add_argument("--start", type=int, default=1, choices=range(1, NUM_STAGES + 1),
                        metavar=f"N (1-{NUM_STAGES})")
    parser.add_argument("--end", type=int, default=NUM_STAGES, choices=range(1, NUM_STAGES + 1),
                        metavar=f"N (1-{NUM_STAGES})")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    active = STAGE_KEYS[args.start - 1 : args.end]
    stop_on_error: bool = cfg.get("runtime", {}).get("stop_on_error", True)

    for step_key in active:
        cmd = build_cmd(step_key, cfg)
        log.info("Running stage: %s", step_key)
        if args.dry_run:
            log.info("[DRY-RUN] %s", " ".join(cmd))
            continue
        result = subprocess.run(cmd)
        if result.returncode != 0:
            log.error("Stage %s failed.", step_key)
            if stop_on_error:
                log.critical("Pipeline halted.")
                return 1

    log.info("Pipeline finished.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
