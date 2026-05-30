"""Canonical identity for compounds and targets — the single source of truth.

Every entry path (batch inject, in-stage add, bulk import, PubChem/UniProt
resolution) builds entity ids and canonical keys here, so the backend can never
drift from the ETL pipeline.

Namespaces are replicated as pinned literals because the backend cannot import
from etl/ (separate venv). They MUST equal the ETL derivations — the parity tests
in test_canonicalize.py enforce that. This module imports only the stdlib, so it
is safe to import from anywhere (no circular-import risk).

Note on the compound key form: the canonical_key uses a double colon
('inchi::{InChIKey}') to match the ETL pipeline byte-for-byte
(etl/compounds/05_build_canonical/run.py). Parity with ETL takes precedence over
the project's usual single-colon '{source}:{id}' convention; do not "fix" this.
"""
from __future__ import annotations

import re
import uuid

# uuid5(NAMESPACE_DNS, "herbaflow.compounds") — must match etl/compounds/utils.py COMPOUND_NS
COMPOUND_NS: uuid.UUID = uuid.UUID("ea972261-ef25-5420-b17c-317f73ec590e")
# uuid5(NAMESPACE_DNS, "herbaflow.targets") — must match etl/disease_targets/utils.py TARGET_NS
TARGET_NS: uuid.UUID = uuid.UUID("421e4557-e00d-533d-ab26-5f7b761b9483")

# UniProt isoform suffix, e.g. the "-2" in "P04637-2". Accessions never contain a
# bare hyphen otherwise, so this only ever strips an isoform tag.
_ISOFORM_SUFFIX = re.compile(r"-\d+$")


def compound_canonical_key(inchikey: str) -> str:
    """ETL-aligned compound canonical key: 'inchi::{InChIKey}' (uppercased, stripped)."""
    return f"inchi::{inchikey.strip().upper()}"


def make_compound_id(inchikey: str) -> str:
    """Deterministic UUID v5 compound id, byte-identical to the ETL pipeline."""
    return str(uuid.uuid5(COMPOUND_NS, compound_canonical_key(inchikey)))


def fold_isoform(accession: str) -> str:
    """Uppercase, strip, and fold a UniProt isoform suffix to its parent accession.

    'P04637-2' -> 'P04637'. Network-level target analysis works at the canonical
    protein, matching ChEMBL / STRING / g:Profiler granularity.
    """
    return _ISOFORM_SUFFIX.sub("", accession.strip().upper())


def target_canonical_key(accession: str) -> str:
    """ETL-aligned target canonical key: 'uniprot:{accession}' (isoform-folded)."""
    return f"uniprot:{fold_isoform(accession)}"


def make_target_id(accession: str) -> str:
    """Deterministic UUID v5 target id, byte-identical to the ETL pipeline."""
    return str(uuid.uuid5(TARGET_NS, target_canonical_key(accession)))
