"""
Plant ETL pipeline orchestrator.

Runs stages extract → normalize_taxonomy → match_gbif → build_canonical_part1
→ build_canonical_part2 → validate → export using settings from plants/settings.yml.

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
    "normalize_taxonomy",
    "match_gbif",
    "build_canonical_part1",
    "resolve_manual_reviews",
    "build_canonical_part2",
    "validate",
    "export",
]
NUM_STAGES = len(STAGE_KEYS)


def build_cmd(step_key: str, cfg: dict) -> list[str]:
    """Build the subprocess command list for a pipeline stage."""
    step = cfg["paths"][step_key]
    script = ETL_ROOT / step["script"]
    src = cfg["source"]
    cmd = [sys.executable, str(script)]

    if step_key == "extract":
        cmd += [
            "--input",
            str(ETL_ROOT / step["input"]),
            "--output-dir",
            str(ETL_ROOT / step["output_dir"]),
            "--output-file",
            step["output_file"],
            "--source-batch-id",
            step.get("source_batch_id", src["batch_id"]),
            "--log-file",
            step["log_file"],
        ]
    elif step_key == "normalize_taxonomy":
        cmd += [
            "--input",
            str(ETL_ROOT / step["input"]),
            "--output-dir",
            str(ETL_ROOT / step["output_dir"]),
            "--output-file",
            step["output_file"],
            "--report-file",
            step["report_file"],
            "--log-file",
            step["log_file"],
        ]
    elif step_key == "match_gbif":
        out_path = ETL_ROOT / step["output_dir"] / step["output_file"]
        ua = cfg.get("gbif", {}).get("user_agent", "herbaflow/1.0")
        cmd += [
            "--input",
            str(ETL_ROOT / step["input"]),
            "--output",
            str(out_path),
            "--cache-dir",
            str(ETL_ROOT / step["cache_dir"]),
            "--user-agent",
            ua,
            "--log-file",
            step["log_file"],
        ]
    elif step_key == "build_canonical_part1":
        cmd += [
            "--input",
            str(ETL_ROOT / step["input"]),
            "--output-dir",
            str(ETL_ROOT / step["output_dir"]),
            "--accepted-file",
            step["accepted_file"],
            "--review-file",
            step["review_file"],
            "--rejected-file",
            step["rejected_file"],
            "--manually-accepted-review-file",
            step["manually_accepted_review_file"],
            "--report-file",
            step["report_file"],
            "--log-file",
            step["log_file"],
            "--source-name",
            src["name"],
        ]
    elif step_key == "resolve_manual_reviews":
        # Fold the curator's manual review decisions (manual_review_decisions.csv)
        # into manually_accepted_review_plants.csv so build_canonical_part2 can
        # merge them. The script self-configures from settings.yml; it no-ops
        # gracefully when no decisions file is present.
        pass
    elif step_key == "build_canonical_part2":
        cmd += [
            "--input",
            str(ETL_ROOT / step["input"]),
            "--manually-accepted-review-input",
            str(ETL_ROOT / step["manually_accepted_review_input"]),
            "--output-dir",
            str(ETL_ROOT / step["output_dir"]),
            "--plants-file",
            step["plants_file"],
            "--aliases-file",
            step["aliases_file"],
            "--report-file",
            step["report_file"],
            "--log-file",
            step["log_file"],
            "--source-name",
            src["name"],
        ]
    elif step_key == "validate":
        cmd += [
            "--plants",
            str(ETL_ROOT / step["plants"]),
            "--aliases",
            str(ETL_ROOT / step["aliases"]),
            "--output-dir",
            str(ETL_ROOT / step["output_dir"]),
            "--report-csv",
            step["report_csv"],
            "--report-json",
            step["report_json"],
            "--validated-plants",
            step["validated_plants"],
            "--validated-aliases",
            step["validated_aliases"],
            "--log-file",
            step["log_file"],
        ]
    elif step_key == "export":
        cmd += [
            "--input-dir",
            str(ETL_ROOT / step["input_dir"]),
            "--output-dir",
            str(ETL_ROOT / step["output_dir"]),
            "--plants-file",
            step["plants_file"],
            "--aliases-file",
            step["aliases_file"],
            "--manifest-file",
            step["manifest_file"],
            "--log-file",
            step["log_file"],
        ]
        if cfg.get("export", {}).get("include_sql", False):
            cmd.append("--emit-sql")

    return cmd


def main() -> int:
    cfg = load_settings("plants")
    log = setup_logging("plants.main", cfg)

    parser = argparse.ArgumentParser(description="Herbaflow Plants ETL Pipeline")
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
