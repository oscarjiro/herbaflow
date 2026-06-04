"""
05_export/run.py — Export canonical tables to final output directory.

Copies targets.csv, target_aliases.csv, disease_targets.csv from
03_build_canonical/out/ to 05_export/out/ and writes an export manifest.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from disease_targets.utils import read_frame, write_frame
from shared.utils import (
    ETL_ROOT,
    ensure_dir,
    load_settings,
    make_run_id,
    now_iso,
    setup_logging,
    write_json,
)

EXPORT_FILES = [
    "targets.csv",
    "target_aliases.csv",
    "disease_targets.csv",
]


def run(cfg: dict, canonical_dir: Path, output_dir: Path) -> int:
    log = setup_logging("disease_targets.05_export", cfg)
    ensure_dir(output_dir)

    src = cfg["source"]
    counts: dict[str, int] = {}

    for filename in EXPORT_FILES:
        src_path = canonical_dir / filename
        if not src_path.exists():
            log.error("Missing canonical file: %s", src_path)
            return 1
        df = read_frame(src_path)
        write_frame(df, output_dir / filename)
        counts[filename.replace(".csv", "")] = len(df)
        log.info("Exported %s: %d rows", filename, len(df))

    diseases_covered = 0
    dt_path = canonical_dir / "disease_targets.csv"
    if dt_path.exists():
        dt_df = read_frame(dt_path)
        if "disease_id" in dt_df.columns:
            diseases_covered = int(dt_df["disease_id"].nunique())

    manifest = {
        "run_id":           make_run_id("export"),
        "batch_id":         src["batch_id"],
        "source":           src["name"],
        "source_url":       src["url"],
        "targets":          counts.get("targets", 0),
        "target_aliases":   counts.get("target_aliases", 0),
        "disease_targets":  counts.get("disease_targets", 0),
        "diseases_covered": diseases_covered,
        "exported_at":      now_iso(),
    }
    write_json(manifest, output_dir / "export_manifest.json")
    log.info(
        "Export complete — targets: %d, aliases: %d, disease_targets: %d, diseases: %d",
        counts.get("targets", 0),
        counts.get("target_aliases", 0),
        counts.get("disease_targets", 0),
        diseases_covered,
    )
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Export disease-target canonical tables")
    parser.add_argument("--canonical-dir", type=Path)
    parser.add_argument("--output-dir",    type=Path)
    args = parser.parse_args()

    cfg   = load_settings("disease_targets")
    paths = cfg["paths"]

    canonical_dir = Path(args.canonical_dir) if args.canonical_dir else ETL_ROOT / paths["canonical_out"]
    output_dir    = Path(args.output_dir)    if args.output_dir    else ETL_ROOT / paths["export_out"]

    sys.exit(run(cfg, canonical_dir, output_dir))
