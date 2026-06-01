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
