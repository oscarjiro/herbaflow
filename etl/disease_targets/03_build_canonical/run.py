"""
03_build_canonical/run.py — Build canonical targets, target_aliases, disease_targets tables.

Reads:
  - 02_normalize/out/targets_raw.csv
  - 02_normalize/out/disease_targets_raw.csv
  - diseases/05_export/out/diseases.csv  (for disease_id lookup)

Writes:
  - targets.csv
  - target_aliases.csv
  - disease_targets.csv
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # etl/
from shared.utils import ETL_ROOT, load_settings, setup_logging, ensure_dir, now_iso, make_run_id, write_json
from disease_targets.utils import (
    read_csv, write_csv, safe_str, validate_required_columns,
    target_id, target_alias_id, disease_target_id,
)

SOURCE_URL_TEMPLATE = "https://platform.opentargets.org/target/{ensembl_id}"


def build_targets(targets_raw: pd.DataFrame, cfg: dict, retrieved_at: str) -> pd.DataFrame:
    src = cfg["source"]
    rows = []
    for _, r in targets_raw.iterrows():
        tid = target_id(r["canonical_key"])
        ensembl = safe_str(r.get("ensembl_id"))
        rows.append({
            "target_id":          tid,
            "canonical_key":      r["canonical_key"],
            "gene_symbol":        safe_str(r.get("gene_symbol")),
            "protein_name":       safe_str(r.get("approved_name")),
            "uniprot_accession":  safe_str(r.get("uniprot_accession")),
            "organism_tax_id":    safe_str(r.get("organism_tax_id", "9606")),
            "source_name":        src["name"],
            "source_url":         SOURCE_URL_TEMPLATE.format(ensembl_id=ensembl),
            "source_batch_id":    src["batch_id"],
            "retrieved_at":       retrieved_at,
            "confidence":         "1.0",
        })
    return pd.DataFrame(rows)


def build_target_aliases(targets_df: pd.DataFrame, cfg: dict, retrieved_at: str) -> pd.DataFrame:
    src = cfg["source"]
    alias_rows = []

    for _, r in targets_df.iterrows():
        tid = r["target_id"]
        ensembl = safe_str(r.get("ensembl_id", ""))
        symbol  = safe_str(r.get("gene_symbol", ""))
        name    = safe_str(r.get("protein_name", ""))
        src_url = r.get("source_url", "")

        def _alias(alias_name: str, alias_type: str) -> dict | None:
            if not alias_name:
                return None
            return {
                "target_alias_id": target_alias_id(tid, alias_name),
                "target_id":       tid,
                "alias_name":      alias_name,
                "alias_key":       alias_name.lower().replace(" ", "_"),
                "alias_type":      alias_type,
                "source_name":     src["name"],
                "source_url":      src_url,
                "source_batch_id": src["batch_id"],
                "retrieved_at":    retrieved_at,
            }

        for row in [
            _alias(ensembl, "ensembl_id"),
            _alias(symbol,  "approved_symbol"),
            _alias(name,    "approved_name"),
        ]:
            if row:
                alias_rows.append(row)

    return pd.DataFrame(alias_rows)


def build_disease_targets(
    dt_raw: pd.DataFrame,
    targets_df: pd.DataFrame,
    diseases_df: pd.DataFrame,
    cfg: dict,
    retrieved_at: str,
) -> pd.DataFrame:
    src = cfg["source"]

    # canonical_key → target_id lookup
    key_to_tid = targets_df.set_index("canonical_key")["target_id"].to_dict()

    # disease_key → disease_id lookup (handle both canonical_key and disease_key columns)
    if "disease_key" in diseases_df.columns:
        key_to_did = diseases_df.set_index("disease_key")["disease_id"].to_dict()
    else:
        key_to_did = diseases_df.set_index("canonical_key")["disease_id"].to_dict()

    rows = []
    skipped = 0
    for _, r in dt_raw.iterrows():
        tid = key_to_tid.get(r["canonical_key"])
        did = safe_str(r.get("disease_id")) or key_to_did.get(r.get("disease_key", ""), "")

        if not tid or not did:
            skipped += 1
            continue

        score = float(r["association_score"])
        rows.append({
            "disease_target_id": disease_target_id(did, tid),
            "disease_id":        did,
            "target_id":         tid,
            "source_name":       src["name"],
            "association_type":  "open_targets_overall",
            "score":             str(score),
            "confidence":        str(round(score, 4)),
            "retrieved_at":      retrieved_at,
        })

    df = pd.DataFrame(rows)
    if not df.empty:
        # Enforce uniqueness on (disease_id, target_id), keeping the highest-score
        # association so dedup reflects best evidence, not source row order.
        # score is stored as a string, so sort on a numeric copy then drop it.
        before = len(df)
        df = (
            df.assign(_score_num=df["score"].astype(float))
            .sort_values("_score_num", ascending=False, kind="stable")
            .drop_duplicates(subset=["disease_id", "target_id"], keep="first")
            .drop(columns="_score_num")
            .reset_index(drop=True)
        )
        if len(df) < before:
            pass  # logged in manifest

    return df, skipped


def run(cfg: dict, normalize_dir: Path, diseases_csv: Path, output_dir: Path) -> int:
    log = setup_logging("disease_targets.03_build_canonical", cfg)
    ensure_dir(output_dir)

    targets_raw = read_csv(normalize_dir / "targets_raw.csv")
    dt_raw      = read_csv(normalize_dir / "disease_targets_raw.csv")
    diseases_df = read_csv(diseases_csv)

    log.info("targets_raw: %d rows", len(targets_raw))
    log.info("disease_targets_raw: %d rows", len(dt_raw))

    # Merge ensembl_id back into targets_raw for alias building
    # targets_raw already has ensembl_id from normalize step
    if "ensembl_id" not in targets_raw.columns:
        log.error("targets_raw.csv missing ensembl_id column")
        return 1

    retrieved_at = now_iso()

    targets_df = build_targets(targets_raw, cfg, retrieved_at)
    write_csv(targets_df, output_dir / "targets.csv")
    log.info("targets.csv: %d rows", len(targets_df))

    # Build aliases (need ensembl_id from raw)
    targets_with_raw = targets_df.copy()
    targets_with_raw["ensembl_id"] = targets_raw["ensembl_id"].values
    aliases_df = build_target_aliases(targets_with_raw, cfg, retrieved_at)
    write_csv(aliases_df, output_dir / "target_aliases.csv")
    log.info("target_aliases.csv: %d rows", len(aliases_df))

    dt_df, skipped = build_disease_targets(dt_raw, targets_df, diseases_df, cfg, retrieved_at)
    write_csv(dt_df, output_dir / "disease_targets.csv")
    log.info("disease_targets.csv: %d rows (%d skipped)", len(dt_df), skipped)

    diseases_covered = dt_df["disease_id"].nunique() if not dt_df.empty else 0

    write_json(
        {
            "run_id":            make_run_id("build_canonical"),
            "targets":           len(targets_df),
            "target_aliases":    len(aliases_df),
            "disease_targets":   len(dt_df),
            "diseases_covered":  diseases_covered,
            "skipped_pairs":     skipped,
            "retrieved_at":      retrieved_at,
        },
        output_dir / "run_manifest.json",
    )

    log.info("Build canonical complete.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Build canonical target tables")
    parser.add_argument("--input-normalize", type=Path)
    parser.add_argument("--input-diseases",  type=Path)
    parser.add_argument("--output-dir",      type=Path)
    args = parser.parse_args()

    cfg   = load_settings("disease_targets")
    paths = cfg["paths"]

    normalize_dir = Path(args.input_normalize) if args.input_normalize else ETL_ROOT / paths["normalize_out"]
    diseases_csv  = Path(args.input_diseases)  if args.input_diseases  else ETL_ROOT / paths["diseases_input"]
    output_dir    = Path(args.output_dir)      if args.output_dir      else ETL_ROOT / paths["canonical_out"]

    sys.exit(run(cfg, normalize_dir, diseases_csv, output_dir))
