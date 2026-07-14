"""
ETL CSV -> Supabase loader.

Load order (respects FK deps):
  plants -> compounds -> plant_compounds -> diseases -> targets -> disease_targets

Loads the trimmed target schema: no canonical_key / source_id / alias tables /
source_systems. Plant identity is carried by gbif_key (derived from the export's
canonical_key 'gbif:{key}' prefix). Empty inchi_key / uniprot_accession are written as
NULL, never '' (the columns are UNIQUE, and '' would collide across the id-less
biologic/non-coding rows).
"""

import argparse
import csv
import os
import sys
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv
from psycopg2 import sql

load_dotenv()

ETL_ROOT = Path(__file__).parent.parent

PLANTS_CSV           = ETL_ROOT / "plants/06_export/out/plants.csv"
COMPOUNDS_CSV        = ETL_ROOT / "compounds/07_export/out/compounds.csv"
PLANT_COMPOUNDS_CSV  = ETL_ROOT / "compounds/07_export/out/plant_compounds.csv"
DISEASES_CSV         = ETL_ROOT / "diseases/05_export/out/diseases.csv"
TARGETS_CSV          = ETL_ROOT / "disease_targets/05_export/out/targets.csv"
DISEASE_TARGETS_CSV  = ETL_ROOT / "disease_targets/05_export/out/disease_targets.csv"


def connect():
    db_url = os.environ["DATABASE_URL"]
    return psycopg2.connect(db_url)


def _conflict(pk: str, update_cols: list[str], upsert: bool) -> str:
    if not upsert:
        return f"on conflict ({pk}) do nothing"
    sets = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
    return f"on conflict ({pk}) do update set {sets}"


def read_csv(path: Path) -> list[dict]:
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _f(val) -> float | None:
    try:
        v = float(val)
        return None if v != v else v  # NaN check
    except (TypeError, ValueError):
        return None


def _i(val) -> int | None:
    try:
        return int(val)
    except (TypeError, ValueError):
        return None


def _ts(val) -> str | None:
    v = val.strip() if isinstance(val, str) else val
    return v if v else None


def _blank_to_none(val) -> str | None:
    """Empty/whitespace natural key -> NULL (the column is UNIQUE; '' would collide)."""
    v = val.strip() if isinstance(val, str) else val
    return v if v else None


def _gbif_key(canonical_key: str | None) -> str | None:
    """Derive gbif_key from the export's canonical_key ('gbif:{key}' -> '{key}')."""
    ck = (canonical_key or "").strip()
    return ck[5:] if ck.startswith("gbif:") else None


# Evidence types that clear the corroboration gate in 04_enrich (structure agrees with the
# raw KNApSAcK formula). Only these map to 'externally_validated'; every other value
# (rejected / no-structure / weak) is 'unvalidated'. 'structure_only' is NOT emitted here —
# it is reserved for the backend manual-entry path (app/services/input_validation.py).
_CORROBORATED_EVIDENCE = {"knapsack+formula", "cas+formula", "name+formula", "cross_source+formula"}


def _validation_status(evidence_type) -> str:
    return "externally_validated" if (evidence_type or "").strip() in _CORROBORATED_EVIDENCE else "unvalidated"


def load_plants(cur, upsert=False):
    print("Loading plants...", end=" ", flush=True)
    rows = read_csv(PLANTS_CSV)
    conflict = _conflict("plant_id", [
        "gbif_key", "canonical_scientific_name", "family_name",
        "source_url", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into plants (
            plant_id, gbif_key, canonical_scientific_name, family_name,
            source_url, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["plant_id"], _gbif_key(r.get("canonical_key")), r.get("canonical_scientific_name"),
        r.get("family_name"), r.get("source_url"), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_compounds(cur, upsert=False):
    print("Loading compounds...", end=" ", flush=True)
    rows = read_csv(COMPOUNDS_CSV)
    conflict = _conflict("compound_id", [
        "canonical_name", "inchi_key", "connectivity_key", "smiles",
        "cas_id", "pubchem_cid", "chembl_id", "molecular_formula", "molecular_weight",
        "tpsa", "logp", "hbond_donors", "hbond_acceptors",
        "rotatable_bonds", "np_likeness_score", "num_ro5_violations",
        "is_pains_positive", "validation_status",
        "source_name", "source_url", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into compounds (
            compound_id, canonical_name, inchi_key, connectivity_key, smiles,
            cas_id, pubchem_cid, chembl_id, molecular_formula, molecular_weight,
            tpsa, logp, hbond_donors, hbond_acceptors,
            rotatable_bonds, np_likeness_score, num_ro5_violations,
            is_pains_positive, validation_status,
            source_name, source_url, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["compound_id"], r.get("canonical_name"),
        _blank_to_none(r.get("inchi_key")), _blank_to_none(r.get("connectivity_key")),
        r.get("smiles"), r.get("cas_id"),
        r.get("pubchem_cid"), r.get("chembl_id"), r.get("molecular_formula"),
        _f(r.get("molecular_weight")),
        _f(r.get("tpsa")), _f(r.get("logp")),
        _i(r.get("hbond_donors")), _i(r.get("hbond_acceptors")),
        _i(r.get("rotatable_bonds")),
        _f(r.get("np_likeness_score")), _i(r.get("num_ro5_violations")),
        str(r.get("is_pains_positive", "")).lower() == "true",
        _validation_status(r.get("evidence_type")),
        _blank_to_none(r.get("source_name")), r.get("source_url"), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_plant_compounds(cur, upsert=False):
    print("Loading plant_compounds...", end=" ", flush=True)
    rows = read_csv(PLANT_COMPOUNDS_CSV)
    conflict = _conflict("plant_compound_id", [
        "plant_id", "compound_id", "source_url", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into plant_compounds (
            plant_compound_id, plant_id, compound_id, source_url, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["plant_compound_id"], r["plant_id"], r["compound_id"],
        r.get("source_url"), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_diseases(cur, upsert=False):
    print("Loading diseases...", end=" ", flush=True)
    rows = read_csv(DISEASES_CSV)
    conflict = _conflict("disease_id", [
        "disease_name", "ontology_id", "ontology_source",
        "source_url", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into diseases (
            disease_id, disease_name, ontology_id, ontology_source,
            source_url, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["disease_id"], r.get("disease_name"),
        r.get("ontology_id"), r.get("ontology_source"),
        r.get("source_url"), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_targets(cur, upsert=False):
    print("Loading targets...", end=" ", flush=True)
    rows = read_csv(TARGETS_CSV)
    conflict = _conflict("target_id", [
        "gene_symbol", "protein_name", "uniprot_accession",
        "source_url", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into targets (
            target_id, gene_symbol, protein_name, uniprot_accession,
            source_url, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["target_id"], r.get("gene_symbol"), r.get("protein_name"),
        _blank_to_none(r.get("uniprot_accession")),
        r.get("source_url"), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_disease_targets(cur, upsert=False):
    print("Loading disease_targets...", end=" ", flush=True)
    rows = read_csv(DISEASE_TARGETS_CSV)
    conflict = _conflict("disease_target_id", [
        "disease_id", "target_id", "association_type", "opentargets_score",
        "source_url", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into disease_targets (
            disease_target_id, disease_id, target_id, association_type, opentargets_score,
            source_url, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["disease_target_id"], r["disease_id"], r["target_id"],
        r.get("association_type"), _f(r.get("score")),
        r.get("source_url"), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


ALL_TABLES = [
    "plants", "compounds", "plant_compounds",
    "diseases", "targets", "disease_targets",
]

# All ETL-managed tables to wipe on --reset (reverse FK dependency order).
RESET_TABLES = [
    "analysis_runs",
    "disease_targets", "targets",
    "diseases",
    "plant_compounds", "compounds",
    "plants",
]


def reset_all_tables(cur) -> None:
    """Truncate all ETL-managed tables in dependency order + CASCADE."""
    print(f"Resetting: {', '.join(RESET_TABLES)}")
    stmt = sql.SQL("TRUNCATE {} CASCADE").format(
        sql.SQL(", ").join(sql.Identifier(t) for t in RESET_TABLES)
    )
    cur.execute(stmt)
    print("All tables cleared.")


def main():
    parser = argparse.ArgumentParser(description="Load ETL CSVs into Supabase")
    parser.add_argument(
        "--tables", nargs="+", choices=ALL_TABLES, metavar="TABLE",
        help=f"Tables to load (default: all). Choices: {', '.join(ALL_TABLES)}",
    )
    parser.add_argument(
        "--upsert", action="store_true",
        help="Replace existing rows on conflict instead of skipping",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help=(
            "Wipe all ETL-managed tables (TRUNCATE CASCADE) then re-seed from "
            "current CSVs. Ignores --tables and --upsert — always loads all "
            "tables fresh."
        ),
    )
    args = parser.parse_args()

    if args.reset:
        tables = set(ALL_TABLES)  # always load everything after a reset
        upsert = False            # tables are empty — no conflicts possible
    else:
        tables = set(args.tables) if args.tables else set(ALL_TABLES)
        upsert = args.upsert

    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()
    try:
        if args.reset:
            reset_all_tables(cur)

        if "plants"           in tables: load_plants(cur, upsert)
        if "compounds"        in tables: load_compounds(cur, upsert)
        if "plant_compounds"  in tables: load_plant_compounds(cur, upsert)
        if "diseases"         in tables: load_diseases(cur, upsert)
        if "targets"          in tables: load_targets(cur, upsert)
        if "disease_targets"  in tables: load_disease_targets(cur, upsert)

        conn.commit()
        print("\nDone.")
    except Exception as e:
        conn.rollback()
        print(f"ERROR: {e}", file=sys.stderr)
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
