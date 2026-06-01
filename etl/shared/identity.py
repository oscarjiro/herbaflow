# etl/shared/identity.py
"""Single source of truth for all Herbaflow entity, alias, and bridge identity.

Every id and canonical_key in the ETL pipeline derives here so the four per-module
utils.py files and the backend canonicalize.py twin cannot drift. Contract:
.superpowers/specs/2026-06-01-s2-identity-unification-design.md and docs/database.md.

Rules:
- canonical_key is single-colon ``{source}:{id}`` (CURIE-style).
- entity_id = uuid5(uuid5(NAMESPACE_DNS, "herbaflow.{table}"), canonical_key).
- bridge_id = uuid5(herbaflow.{bridge}, "{left_id}:{right_id}")  (pair grain; source NOT in identity).
- alias_id  = uuid5(herbaflow.{x}_aliases, "{parent_id}:{alias_key}")  (alias_key is a slug).

stdlib-only (no pandas) so it is importable from any step or the backend twin.
"""
from __future__ import annotations

import re
import uuid

# --- Namespaces: uuid5(NAMESPACE_DNS, "herbaflow.{table}") ---
PLANT_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.plants")
COMPOUND_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.compounds")
TARGET_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.targets")
DISEASE_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.diseases")
PLANT_ALIAS_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.plant_aliases")
COMPOUND_ALIAS_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.compound_aliases")
TARGET_ALIAS_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.target_aliases")
DISEASE_ALIAS_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.disease_aliases")
PLANT_COMPOUND_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.plant_compounds")
COMPOUND_TARGET_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.compound_targets")
DISEASE_TARGET_NS = uuid.uuid5(uuid.NAMESPACE_DNS, "herbaflow.disease_targets")

_ISOFORM_SUFFIX = re.compile(r"-\d+$")


def _v5(namespace: uuid.UUID, key: str) -> str:
    return str(uuid.uuid5(namespace, key))


def slugify(value: object) -> str:
    """Lowercase; collapse runs of non-alphanumerics to single '_'; trim leading/trailing '_'."""
    text = re.sub(r"\s+", " ", str(value or "")).strip().lower()
    text = re.sub(r"[^a-z0-9]+", "_", text)
    return re.sub(r"_+", "_", text).strip("_")


# --- Canonical-key cascades ({source}:{id}, single colon) ---

def plant_canonical_key(gbif_usage_key: object, name_slug_source: object = "") -> str:
    key = str(gbif_usage_key or "").strip()
    if key:
        return f"gbif:{key}"
    return f"plant:{slugify(name_slug_source)}"


def fold_isoform(accession: str) -> str:
    """'P04637-2' -> 'P04637' (uppercased, stripped)."""
    return _ISOFORM_SUFFIX.sub("", str(accession).strip().upper())


def _norm(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def compound_canonical_key(candidate: dict) -> str:
    """Port of canonical_identity_for_candidate, single-colon, inchi->inchikey.

    Priority: inchi_key > pubchem_cid > chembl_id > cas_id > name_formula > name > formula.
    Returns '' when no identity is available.
    """
    inchi = _norm(candidate.get("inchi_key"))
    pubchem = _norm(candidate.get("pubchem_cid"))
    chembl = _norm(candidate.get("chembl_id"))
    cas = _norm(candidate.get("cas_id") or candidate.get("representative_cas_id"))
    name = slugify(candidate.get("preferred_name") or candidate.get("iupac_name")
                   or candidate.get("representative_name"))
    formula = slugify(candidate.get("molecular_formula") or candidate.get("representative_formula"))
    if inchi:
        return f"inchikey:{inchi.upper()}"
    if pubchem:
        return f"pubchem:{pubchem}"
    if chembl:
        return f"chembl:{chembl}"
    if cas:
        return f"cas:{slugify(cas)}"
    if name and formula:
        return f"name_formula:{name}:{formula}"
    if name:
        return f"name:{name}"
    if formula:
        return f"formula:{formula}"
    return ""


def target_canonical_key(uniprot: object = None, ensembl: object = None, gene: object = None) -> str:
    acc = str(uniprot or "").strip()
    if acc:
        return f"uniprot:{fold_isoform(acc)}"
    ens = str(ensembl or "").strip()
    if ens:
        return f"ensembl:{ens}"
    sym = str(gene or "").strip()
    if sym:
        return f"gene:{sym.upper()}"
    raise ValueError("target_canonical_key requires uniprot, ensembl, or gene")


_ONTOLOGY_PREFIX = {"disease ontology": "doid", "doid": "doid", "mesh": "mesh"}


def disease_canonical_key(ontology_source: object, ontology_id: object, slug_source: object) -> str:
    src = str(ontology_source or "").strip().lower()
    oid = str(ontology_id or "").strip()
    prefix = _ONTOLOGY_PREFIX.get(src)
    if oid and prefix:
        local = re.sub(rf"^{prefix}[:_]", "", oid, flags=re.IGNORECASE)
        return f"{prefix}:{local}"
    return f"disease:{slugify(slug_source)}"


# --- Entity ids: uuid5(NS, canonical_key) ---

def plant_id(gbif_usage_key: object, name_slug_source: object = "") -> str:
    return _v5(PLANT_NS, plant_canonical_key(gbif_usage_key, name_slug_source))


def compound_id(candidate: dict) -> str:
    return _v5(COMPOUND_NS, compound_canonical_key(candidate))


def compound_id_from_key(canonical_key: str) -> str:
    return _v5(COMPOUND_NS, canonical_key)


def target_id(uniprot: object = None, ensembl: object = None, gene: object = None) -> str:
    return _v5(TARGET_NS, target_canonical_key(uniprot, ensembl, gene))


def target_id_from_key(canonical_key: str) -> str:
    return _v5(TARGET_NS, canonical_key)


def disease_id(ontology_source: object, ontology_id: object, slug_source: object) -> str:
    return _v5(DISEASE_NS, disease_canonical_key(ontology_source, ontology_id, slug_source))


# --- Aliases: key on (parent_id, alias_key-slug); alias_type is an attribute ---

# Verbatim from diseases/03_build_canonical (single source now). Higher int = higher priority.
ALIAS_PRIORITY = {
    "canonical_name": 100,
    "ontology_synonym": 90,
    "ontology_label": 85,
    "user_alias": 70,
    "normalized_alias": 60,
    "seed_name": 50,
    "raw_name": 40,
}


def _alias_id(namespace: uuid.UUID, parent_id: str, alias_key: str) -> str:
    return _v5(namespace, f"{parent_id}:{alias_key}")


def plant_alias_id(parent_id: str, alias_key: str) -> str:
    return _alias_id(PLANT_ALIAS_NS, parent_id, alias_key)


def compound_alias_id(parent_id: str, alias_key: str) -> str:
    return _alias_id(COMPOUND_ALIAS_NS, parent_id, alias_key)


def target_alias_id(parent_id: str, alias_key: str) -> str:
    return _alias_id(TARGET_ALIAS_NS, parent_id, alias_key)


def disease_alias_id(parent_id: str, alias_key: str) -> str:
    return _alias_id(DISEASE_ALIAS_NS, parent_id, alias_key)


def pick_alias(current: dict, candidate: dict) -> dict:
    """Return whichever alias has the higher ALIAS_PRIORITY (candidate wins only if strictly >)."""
    if current is None:
        return candidate
    cur_p = ALIAS_PRIORITY.get(current.get("alias_type"), 0)
    cand_p = ALIAS_PRIORITY.get(candidate.get("alias_type"), 0)
    return candidate if cand_p > cur_p else current


# --- Bridges: pair grain; uuid5(NS, "{left_id}:{right_id}"); source NOT in identity ---

def plant_compound_id(plant_id: str, compound_id: str) -> str:
    return _v5(PLANT_COMPOUND_NS, f"{plant_id}:{compound_id}")


def compound_target_id(compound_id: str, target_id: str) -> str:
    return _v5(COMPOUND_TARGET_NS, f"{compound_id}:{target_id}")


def disease_target_id(disease_id: str, target_id: str) -> str:
    return _v5(DISEASE_TARGET_NS, f"{disease_id}:{target_id}")
