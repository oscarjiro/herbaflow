"""
Root-level runner for the plant ETL pipeline.

Logical stages:
    1. extract
    2. normalize_taxonomy
    3. match_gbif
    4. build_canonical
    5. validate
    6. export

Default folder layout used by this runner:
    01_extract/out/
    02_normalize_taxonomy/out/
    03_match_gbif/out/
    04_build_canonical/out/
    05_validate/out/
    06_export/out/

The runner discovers the stage scripts automatically inside each stage folder,
or uses overrides from 00_config/settings.yml if present.

Features:
- run full pipeline or a selected step range
- read settings from 00_config/settings.yml if present
- pass explicit input/output paths between steps
- stop on failure
- dry-run mode
"""

import sys
import yaml
import argparse
import subprocess
import logging
from pathlib import Path
from datetime import datetime


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def load_settings(path: Path) -> dict:
    if not path.exists():
        logging.error(f"Settings file not found at {path}")
        sys.exit(1)
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


class HerbaflowRunner:
    def __init__(self, settings: dict, dry_run: bool = False):
        self.settings = settings
        self.dry_run = dry_run
        self.steps = settings.get("paths", {}).get("steps", {})
        self.order = [
            "extract",
            "normalize_taxonomy",
            "match_gbif",
            "build_canonical_part1",
            "build_canonical_part2",
            "validate",
            "export",
        ]

    def run_step(self, step_key: str) -> bool:
        cfg = self.steps.get(step_key)
        if not cfg or "script" not in cfg:
            logging.error(f"Step configuration missing for: {step_key}")
            return False

        script_path = Path(cfg["script"])
        if not script_path.exists():
            logging.error(f"Script file not found: {script_path}")
            return False

        cmd = [sys.executable, str(script_path)]

        # --- 01_EXTRACT ---
        if step_key == "extract":
            cmd += [
                "--input",
                cfg["input"],
                "--output-dir",
                cfg["output_dir"],
                "--output-file",
                cfg["output_file"],
                "--source-batch-id",
                cfg.get(
                    "source_batch_id",
                    "knapsack_gen_" + datetime.now().strftime("%Y_%m_%d"),
                ),
                "--log-file",
                cfg["log_file"],
            ]

        # --- 02_NORMALIZE_TAXONOMY ---
        elif step_key == "normalize_taxonomy":
            cmd += [
                "--input",
                cfg["input"],
                "--output-dir",
                cfg["output_dir"],
                "--output-file",
                cfg["output_file"],
                "--report-file",
                cfg["report_file"],
                "--log-file",
                cfg["log_file"],
            ]

        # --- 03_MATCH_GBIF ---
        elif step_key == "match_gbif":
            ua = self.settings.get("gbif", {}).get("user_agent", "herbaflow/1.0")
            # Stage 03 uses --output (path to file) NOT --output-dir
            out_path = Path(cfg["output_dir"]) / cfg["output_file"]
            cmd += [
                "--input",
                cfg["input"],
                "--output",
                str(out_path),
                "--cache-dir",
                cfg["cache_dir"],
                "--user-agent",
                ua,
                "--log-file",
                cfg["log_file"],
            ]

        # --- 04_BUILD_CANONICAL_PART1 ---
        elif step_key == "build_canonical_part1":
            cmd += [
                "--input",
                cfg["input"],
                "--output-dir",
                cfg["output_dir"],
                "--accepted-file",
                cfg["accepted_file"],
                "--review-file",
                cfg["review_file"],
                "--rejected-file",
                cfg["rejected_file"],
                "--manually-accepted-review-file",
                cfg["manually_accepted_review_file"],
                "--report-file",
                cfg["report_file"],
                "--log-file",
                cfg["log_file"],
                "--source-name",
                self.settings.get("source", {}).get("name", "KNApSAcK World"),
            ]

        # --- 04_BUILD_CANONICAL_PART2 ---
        elif step_key == "build_canonical_part2":
            cmd += [
                "--input",
                cfg["input"],
                "--manually-accepted-review-input",
                cfg["manually_accepted_review_input"],
                "--output-dir",
                cfg["output_dir"],
                "--plants-file",
                cfg["plants_file"],
                "--aliases-file",
                cfg["aliases_file"],
                "--report-file",
                cfg["report_file"],
                "--log-file",
                cfg["log_file"],
                "--source-name",
                self.settings.get("source", {}).get("name", "KNApSAcK World"),
            ]

        # --- 05_VALIDATE ---
        elif step_key == "validate":
            cmd += [
                "--plants",
                cfg["plants"],
                "--aliases",
                cfg["aliases"],
                "--output-dir",
                cfg["output_dir"],
                "--report-csv",
                cfg["report_csv"],
                "--report-json",
                cfg["report_json"],
                "--validated-plants",
                cfg["validated_plants"],
                "--validated-aliases",
                cfg["validated_aliases"],
                "--log-file",
                cfg["log_file"],
            ]

        # --- 06_EXPORT ---
        elif step_key == "export":
            cmd += [
                "--input-dir",
                cfg["input_dir"],
                "--output-dir",
                cfg["output_dir"],
                "--plants-file",
                cfg["plants_file"],
                "--aliases-file",
                cfg["aliases_file"],
                "--manifest-file",
                cfg["manifest_file"],
                "--log-file",
                cfg["log_file"],
            ]
            if self.settings.get("export", {}).get("include_sql", False):
                cmd.append("--emit-sql")

        # --- Execution ---
        logging.info(f"🚀 Running Stage: {step_key}")
        if self.dry_run:
            logging.info(f"[DRY-RUN] Command: {' '.join(cmd)}")
            return True

        try:
            subprocess.run(cmd, check=True)
            return True
        except subprocess.CalledProcessError:
            logging.error(f"❌ Stage {step_key} failed.")
            return False


def main():
    parser = argparse.ArgumentParser(description="Herbaflow ETL Pipeline Runner")
    parser.add_argument("--start", choices=range(1, 8), type=int, default=1)
    parser.add_argument("--end", choices=range(1, 8), type=int, default=7)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    setup_logging()
    settings = load_settings(Path("00_settings/settings.yml"))
    runner = HerbaflowRunner(settings, dry_run=args.dry_run)

    active_stages = runner.order[args.start - 1 : args.end]

    for step_key in active_stages:
        if not runner.run_step(step_key):
            if settings.get("runtime", {}).get("stop_on_error", True):
                logging.critical("🛑 Pipeline halted.")
                sys.exit(1)

    logging.info("✨ Pipeline finished.")


if __name__ == "__main__":
    main()
