"""
Compound ETL pipeline orchestrator.

Runs stages extract → normalize → dedupe_candidates → enrich →
build_canonical → validate → export using settings from compounds/settings.yml.

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
    "extract",
    "normalize",
    "dedupe_candidates",
    "enrich",
    "build_canonical",
    "validate",
    "export",
]
NUM_STAGES = len(STAGE_KEYS)

STAGE_SCRIPTS = {
    "extract": "compounds/01_extract/run.py",
    "normalize": "compounds/02_normalize/run.py",
    "dedupe_candidates": "compounds/03_dedupe_candidates/run.py",
    "enrich": "compounds/04_enrich/run.py",
    "build_canonical": "compounds/05_build_canonical/run.py",
    "validate": "compounds/06_validate/run.py",
    "export": "compounds/07_export/run.py",
}


def build_cmd(step_key: str) -> list[str]:
    """Build the subprocess command for a compound pipeline stage.

    Every stage resolves its own inputs and outputs from compounds/settings.yml
    via load_settings("compounds"); each stage's argparse accepts only --settings
    plus optional --input overrides. The orchestrator therefore invokes the stage
    script with no path arguments — passing stage-specific path flags would be
    rejected by argparse and halt the pipeline.
    """
    script = ETL_ROOT / STAGE_SCRIPTS[step_key]
    return [sys.executable, str(script)]


def main() -> int:
    cfg = load_settings("compounds")
    log = setup_logging("compounds.main", cfg)

    parser = argparse.ArgumentParser(description="Herbaflow Compounds ETL Pipeline")
    parser.add_argument(
        "--start",
        type=int,
        default=1,
        choices=range(1, NUM_STAGES + 1),
        metavar=f"N (1-{NUM_STAGES})",
    )
    parser.add_argument(
        "--end",
        type=int,
        default=NUM_STAGES,
        choices=range(1, NUM_STAGES + 1),
        metavar=f"N (1-{NUM_STAGES})",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    active = STAGE_KEYS[args.start - 1 : args.end]
    stop_on_error: bool = cfg.get("runtime", {}).get("stop_on_error", True)

    for step_key in active:
        cmd = build_cmd(step_key)
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
