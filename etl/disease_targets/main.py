"""
Disease-targets ETL pipeline orchestrator.

Runs stages: fetch -> normalize -> build_canonical -> validate -> export

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
    "fetch",
    "normalize",
    "build_canonical",
    "validate",
    "export",
]
NUM_STAGES = len(STAGE_KEYS)

STAGE_SCRIPTS = {
    "fetch": "disease_targets/01_fetch/run.py",
    "normalize": "disease_targets/02_normalize/run.py",
    "build_canonical": "disease_targets/03_build_canonical/run.py",
    "validate": "disease_targets/04_validate/run.py",
    "export": "disease_targets/05_export/run.py",
}


def build_cmd(step_key: str, cfg: dict) -> list[str]:
    script = ETL_ROOT / STAGE_SCRIPTS[step_key]
    paths = cfg["paths"]
    cmd = [sys.executable, str(script)]

    if step_key == "fetch":
        cmd += [
            "--input-diseases",
            str(ETL_ROOT / paths["diseases_input"]),
            "--output-dir",
            str(ETL_ROOT / paths["fetch_out"]),
            "--cache-dir",
            str(ETL_ROOT / paths["cache_dir"]),
        ]
    elif step_key == "normalize":
        cmd += [
            "--input-dir",
            str(ETL_ROOT / paths["fetch_out"]),
            "--output-dir",
            str(ETL_ROOT / paths["normalize_out"]),
        ]
    elif step_key == "build_canonical":
        cmd += [
            "--input-normalize",
            str(ETL_ROOT / paths["normalize_out"]),
            "--input-diseases",
            str(ETL_ROOT / paths["diseases_input"]),
            "--output-dir",
            str(ETL_ROOT / paths["canonical_out"]),
        ]
    elif step_key == "validate":
        cmd += [
            "--canonical-dir",
            str(ETL_ROOT / paths["canonical_out"]),
            "--diseases-csv",
            str(ETL_ROOT / paths["diseases_input"]),
            "--output-dir",
            str(ETL_ROOT / paths["validate_out"]),
        ]
    elif step_key == "export":
        cmd += [
            "--canonical-dir",
            str(ETL_ROOT / paths["canonical_out"]),
            "--output-dir",
            str(ETL_ROOT / paths["export_out"]),
        ]

    return cmd


def main() -> int:
    cfg = load_settings("disease_targets")
    log = setup_logging("disease_targets.main", cfg)

    parser = argparse.ArgumentParser(
        description="Herbaflow Disease-Targets ETL Pipeline"
    )
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
