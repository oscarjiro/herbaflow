"""
ETL CSV -> Supabase loader.

Load order (respects FK deps):
  source_systems (already seeded) ->
  import_batches (created here) ->
  plants -> plant_aliases ->
  compounds -> compound_aliases -> plant_compounds ->
  diseases -> disease_aliases ->
  targets -> target_aliases -> disease_targets
"""

import argparse
import csv
import os
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

import psycopg2
import psycopg2.extras
from dotenv import load_dotenv

load_dotenv()

ETL_ROOT = Path(__file__).parent.parent
DB_URL = os.environ["DATABASE_URL"]

PLANTS_CSV           = ETL_ROOT / "plants/06_export/out/plants.csv"
PLANT_ALIASES_CSV    = ETL_ROOT / "plants/06_export/out/plant_aliases.csv"
COMPOUNDS_CSV        = ETL_ROOT / "compounds/07_export/out/compounds.csv"
COMPOUND_ALIASES_CSV = ETL_ROOT / "compounds/07_export/out/compound_aliases.csv"
PLANT_COMPOUNDS_CSV  = ETL_ROOT / "compounds/07_export/out/plant_compounds.csv"
DISEASES_CSV         = ETL_ROOT / "diseases/05_export/out/diseases.csv"
DISEASE_ALIASES_CSV  = ETL_ROOT / "diseases/05_export/out/disease_aliases.csv"
TARGETS_CSV          = ETL_ROOT / "disease_targets/05_export/out/targets.csv"
TARGET_ALIASES_CSV   = ETL_ROOT / "disease_targets/05_export/out/target_aliases.csv"
DISEASE_TARGETS_CSV  = ETL_ROOT / "disease_targets/05_export/out/disease_targets.csv"


def connect():
    return psycopg2.connect(DB_URL)


def _conflict(pk: str, update_cols: list[str], upsert: bool) -> str:
    if not upsert:
        return f"on conflict ({pk}) do nothing"
    sets = ", ".join(f"{c} = excluded.{c}" for c in update_cols)
    return f"on conflict ({pk}) do update set {sets}"


def load_source_map(cur) -> dict:
    cur.execute("select source_name, source_id from source_systems")
    return {row[0]: str(row[1]) for row in cur.fetchall()}


def resolve_src(row: dict, source_map: dict) -> str | None:
    val = row.get("source_name", "")
    return source_map[val] if val and val in source_map else None


def create_batch(cur, step_name: str) -> str:
    batch_id = str(uuid.uuid4())
    cur.execute(
        "insert into import_batches (batch_id, step_name, status, started_at) values (%s,%s,%s,%s)",
        (batch_id, step_name, "completed", datetime.now(timezone.utc)),
    )
    return batch_id


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


def load_plants(cur, source_map, batch_id, upsert=False):
    print("Loading plants...", end=" ", flush=True)
    rows = read_csv(PLANTS_CSV)
    conflict = _conflict("plant_id", [
        "canonical_key", "canonical_scientific_name", "authorship",
        "family_name", "taxonomic_status", "rank",
        "gbif_usage_key", "gbif_accepted_usage_key", "gbif_species_key",
        "gbif_genus_key", "gbif_family_key", "gbif_kingdom_key",
        "source_id", "source_url", "source_batch_id", "retrieved_at", "confidence",
    ], upsert)
    sql = f"""
        insert into plants (
            plant_id, canonical_key, canonical_scientific_name, authorship,
            family_name, taxonomic_status, rank,
            gbif_usage_key, gbif_accepted_usage_key, gbif_species_key,
            gbif_genus_key, gbif_family_key, gbif_kingdom_key,
            source_id, source_url, source_batch_id, retrieved_at, confidence
        ) values %s {conflict}
    """
    data = [(
        r["plant_id"], r["canonical_key"], r.get("canonical_scientific_name"),
        r.get("authorship"), r.get("family_name"), r.get("taxonomic_status"), r.get("rank"),
        _i(r.get("gbif_usage_key")), _i(r.get("gbif_accepted_usage_key")),
        _i(r.get("gbif_species_key")), _i(r.get("gbif_genus_key")),
        _i(r.get("gbif_family_key")), _i(r.get("gbif_kingdom_key")),
        resolve_src(r, source_map), r.get("source_url"), batch_id,
        _ts(r.get("retrieved_at")), _f(r.get("confidence")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_plant_aliases(cur, source_map, batch_id, upsert=False):
    print("Loading plant_aliases...", end=" ", flush=True)
    rows = read_csv(PLANT_ALIASES_CSV)
    conflict = _conflict("alias_id", [
        "plant_id", "alias_name", "alias_key", "alias_type",
        "source_id", "source_url", "source_batch_id", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into plant_aliases (
            alias_id, plant_id, alias_name, alias_key, alias_type,
            source_id, source_url, source_batch_id, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["alias_id"], r["plant_id"], r.get("alias_name"), r.get("alias_key"),
        r.get("alias_type"), resolve_src(r, source_map),
        r.get("source_url"), batch_id, _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_compounds(cur, source_map, batch_id, upsert=False):
    print("Loading compounds...", end=" ", flush=True)
    rows = read_csv(COMPOUNDS_CSV)
    conflict = _conflict("compound_id", [
        "canonical_key", "canonical_name", "inchi_key", "smiles",
        "cas_id", "pubchem_cid", "chembl_id", "molecular_formula", "molecular_weight",
        "tpsa", "logp", "hbond_donors", "hbond_acceptors",
        "rotatable_bonds", "qed_score", "np_likeness_score", "num_ro5_violations",
        "lipinski_source",
        "source_id", "source_url", "source_batch_id", "retrieved_at", "confidence",
    ], upsert)
    sql = f"""
        insert into compounds (
            compound_id, canonical_key, canonical_name, inchi_key, smiles,
            cas_id, pubchem_cid, chembl_id, molecular_formula, molecular_weight,
            tpsa, logp, hbond_donors, hbond_acceptors,
            rotatable_bonds, qed_score, np_likeness_score, num_ro5_violations,
            lipinski_source, is_pains_positive,
            source_id, source_url, source_batch_id, retrieved_at, confidence
        ) values %s {conflict}
    """
    data = [(
        r["compound_id"], r["canonical_key"], r.get("canonical_name"),
        r.get("inchi_key"), r.get("smiles"), r.get("cas_id"),
        r.get("pubchem_cid"), r.get("chembl_id"), r.get("molecular_formula"),
        _f(r.get("molecular_weight")),
        _f(r.get("tpsa")), _f(r.get("logp")),
        _i(r.get("hbond_donors")), _i(r.get("hbond_acceptors")),
        _i(r.get("rotatable_bonds")), _f(r.get("qed_score")),
        _f(r.get("np_likeness_score")), _i(r.get("num_ro5_violations")),
        r.get("lipinski_source") or None,
        str(r.get("is_pains_positive", "")).lower() == "true",
        resolve_src(r, source_map), r.get("source_url"), batch_id,
        _ts(r.get("retrieved_at")), _f(r.get("confidence")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_compound_aliases(cur, source_map, batch_id, upsert=False):
    print("Loading compound_aliases...", end=" ", flush=True)
    rows = read_csv(COMPOUND_ALIASES_CSV)
    conflict = _conflict("compound_alias_id", [
        "compound_id", "alias_name", "alias_key", "alias_type",
        "source_id", "source_url", "source_batch_id", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into compound_aliases (
            compound_alias_id, compound_id, alias_name, alias_key, alias_type,
            source_id, source_url, source_batch_id, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["compound_alias_id"], r["compound_id"], r.get("alias_name"), r.get("alias_key"),
        r.get("alias_type"), resolve_src(r, source_map),
        r.get("source_url"), batch_id, _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_plant_compounds(cur, source_map, batch_id, upsert=False):
    print("Loading plant_compounds...", end=" ", flush=True)
    rows = read_csv(PLANT_COMPOUNDS_CSV)
    conflict = _conflict("plant_compound_id", [
        "plant_id", "compound_id",
        "source_plant_raw_id", "source_compound_raw_id",
        "source_id", "evidence_type", "confidence", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into plant_compounds (
            plant_compound_id, plant_id, compound_id,
            source_plant_raw_id, source_compound_raw_id,
            source_id, evidence_type, confidence, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["plant_compound_id"], r["plant_id"], r["compound_id"],
        r.get("source_plant_raw_id"), r.get("source_compound_raw_id"),
        resolve_src(r, source_map), r.get("evidence_type"),
        _f(r.get("confidence")), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_diseases(cur, source_map, batch_id, upsert=False):
    print("Loading diseases...", end=" ", flush=True)
    rows = read_csv(DISEASES_CSV)
    conflict = _conflict("disease_id", [
        "canonical_key", "disease_name", "ontology_id", "ontology_source",
        "source_id", "source_url", "source_batch_id", "retrieved_at", "confidence",
    ], upsert)
    sql = f"""
        insert into diseases (
            disease_id, canonical_key, disease_name, ontology_id, ontology_source,
            source_id, source_url, source_batch_id, retrieved_at, confidence
        ) values %s {conflict}
    """
    data = [(
        r["disease_id"], r.get("canonical_key"), r.get("disease_name"),
        r.get("ontology_id"), r.get("ontology_source"),
        resolve_src(r, source_map), r.get("source_url"), batch_id,
        _ts(r.get("retrieved_at")), _f(r.get("confidence")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_disease_aliases(cur, source_map, batch_id, upsert=False):
    print("Loading disease_aliases...", end=" ", flush=True)
    rows = read_csv(DISEASE_ALIASES_CSV)
    conflict = _conflict("disease_alias_id", [
        "disease_id", "alias_name", "alias_key", "alias_type",
        "source_id", "source_url", "source_batch_id", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into disease_aliases (
            disease_alias_id, disease_id, alias_name, alias_key, alias_type,
            source_id, source_url, source_batch_id, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r.get("disease_alias_id") or r.get("alias_id"),
        r["disease_id"], r.get("alias_name"), r.get("alias_key"), r.get("alias_type"),
        resolve_src(r, source_map), r.get("source_url"), batch_id, _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_targets(cur, source_map, batch_id, upsert=False):
    print("Loading targets...", end=" ", flush=True)
    rows = read_csv(TARGETS_CSV)
    conflict = _conflict("target_id", [
        "canonical_key", "gene_symbol", "protein_name",
        "uniprot_accession", "organism_tax_id",
        "source_id", "source_url", "source_batch_id", "retrieved_at", "confidence",
    ], upsert)
    sql = f"""
        insert into targets (
            target_id, canonical_key, gene_symbol, protein_name,
            uniprot_accession, organism_tax_id,
            source_id, source_url, source_batch_id, retrieved_at, confidence
        ) values %s {conflict}
    """
    data = [(
        r["target_id"], r.get("canonical_key"), r.get("gene_symbol"), r.get("protein_name"),
        r.get("uniprot_accession"), _i(r.get("organism_tax_id")),
        resolve_src(r, source_map), r.get("source_url"), batch_id,
        _ts(r.get("retrieved_at")), _f(r.get("confidence")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_target_aliases(cur, source_map, batch_id, upsert=False):
    print("Loading target_aliases...", end=" ", flush=True)
    rows = read_csv(TARGET_ALIASES_CSV)
    conflict = _conflict("target_alias_id", [
        "target_id", "alias_name", "alias_key", "alias_type",
        "source_id", "source_url", "source_batch_id", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into target_aliases (
            target_alias_id, target_id, alias_name, alias_key, alias_type,
            source_id, source_url, source_batch_id, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["target_alias_id"], r["target_id"], r.get("alias_name"), r.get("alias_key"),
        r.get("alias_type"), resolve_src(r, source_map),
        r.get("source_url"), batch_id, _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


def load_disease_targets(cur, source_map, batch_id, upsert=False):
    print("Loading disease_targets...", end=" ", flush=True)
    rows = read_csv(DISEASE_TARGETS_CSV)
    conflict = _conflict("disease_target_id", [
        "disease_id", "target_id",
        "source_id", "association_type", "score", "confidence", "retrieved_at",
    ], upsert)
    sql = f"""
        insert into disease_targets (
            disease_target_id, disease_id, target_id,
            source_id, association_type, score, confidence, retrieved_at
        ) values %s {conflict}
    """
    data = [(
        r["disease_target_id"], r["disease_id"], r["target_id"],
        resolve_src(r, source_map), r.get("association_type"),
        _f(r.get("score")), _f(r.get("confidence")), _ts(r.get("retrieved_at")),
    ) for r in rows]
    psycopg2.extras.execute_values(cur, sql, data, page_size=500)
    print(len(data))


ALL_TABLES = [
    "plants", "plant_aliases",
    "compounds", "compound_aliases", "plant_compounds",
    "diseases", "disease_aliases",
    "targets", "target_aliases", "disease_targets",
]

# All ETL-managed tables to wipe on --reset (reverse FK dependency order).
# Excludes source_systems (pre-seeded reference data, never wiped).
RESET_TABLES = [
    "analysis_runs",
    "import_batches",
    "disease_targets", "target_aliases", "targets",
    "disease_aliases", "diseases",
    "plant_compounds", "compound_aliases", "compounds",
    "plant_aliases", "plants",
]


def reset_all_tables(cur) -> None:
    """Truncate all ETL-managed tables in dependency order + CASCADE."""
    tables_sql = ", ".join(RESET_TABLES)
    print(f"Resetting: {tables_sql}")
    cur.execute(f"TRUNCATE {tables_sql} CASCADE")
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
            "tables fresh. Preserves source_systems."
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
        source_map = load_source_map(cur)
        print(f"source_systems: {len(source_map)} entries")

        if args.reset:
            reset_all_tables(cur)

        plants_batch    = create_batch(cur, "etl/plants/06_export")    if tables & {"plants", "plant_aliases"}                     else None
        compounds_batch = create_batch(cur, "etl/compounds/07_export") if tables & {"compounds", "compound_aliases", "plant_compounds"} else None
        diseases_batch  = create_batch(cur, "etl/diseases/05_export")  if tables & {"diseases", "disease_aliases"}                  else None
        targets_batch   = create_batch(cur, "etl/disease_targets/05_export") if tables & {"targets", "target_aliases", "disease_targets"} else None

        if "plants"           in tables: load_plants(cur, source_map, plants_batch, upsert)
        if "plant_aliases"    in tables: load_plant_aliases(cur, source_map, plants_batch, upsert)
        if "compounds"        in tables: load_compounds(cur, source_map, compounds_batch, upsert)
        if "compound_aliases" in tables: load_compound_aliases(cur, source_map, compounds_batch, upsert)
        if "plant_compounds"  in tables: load_plant_compounds(cur, source_map, compounds_batch, upsert)
        if "diseases"         in tables: load_diseases(cur, source_map, diseases_batch, upsert)
        if "disease_aliases"  in tables: load_disease_aliases(cur, source_map, diseases_batch, upsert)
        if "targets"          in tables: load_targets(cur, source_map, targets_batch, upsert)
        if "target_aliases"   in tables: load_target_aliases(cur, source_map, targets_batch, upsert)
        if "disease_targets"  in tables: load_disease_targets(cur, source_map, targets_batch, upsert)

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
