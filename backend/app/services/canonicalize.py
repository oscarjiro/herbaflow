"""Canonical identity for compounds and targets — the single source of truth.

Every entry path (batch inject, in-stage add, bulk import, PubChem/UniProt
resolution) builds entity ids and canonical keys here, so the backend can never
drift from the ETL pipeline.

Namespaces are replicated as pinned literals because the backend cannot import
from etl/ (separate venv). They MUST equal the ETL derivations — the parity tests
in test_canonicalize.py enforce that. This module imports only the stdlib, so it
is safe to import from anywhere (no circular-import risk).

Note on the compound key form: the canonical_key uses a single colon
('inchikey:{InChIKey}'), re-keyed in S2 to match etl/shared/identity.py
byte-for-byte and to follow the project's '{source}:{id}' convention. Parity with
ETL is enforced by the tests in test_canonicalize.py.
"""
from __future__ import annotations

import re
import uuid

# uuid5(NAMESPACE_DNS, "herbaflow.compounds") — must match etl/compounds/utils.py COMPOUND_NS
COMPOUND_NS: uuid.UUID = uuid.UUID("ea972261-ef25-5420-b17c-317f73ec590e")
# uuid5(NAMESPACE_DNS, "herbaflow.targets") — must match etl/disease_targets/utils.py TARGET_NS
TARGET_NS: uuid.UUID = uuid.UUID("421e4557-e00d-533d-ab26-5f7b761b9483")
# uuid5(NAMESPACE_DNS, "herbaflow.compound_targets") — must match etl/shared/identity.py COMPOUND_TARGET_NS
COMPOUND_TARGET_NS: uuid.UUID = uuid.UUID("59a665ef-1743-5e45-98c2-128fe7e345a9")

# UniProt isoform suffix, e.g. the "-2" in "P04637-2". Accessions never contain a
# bare hyphen otherwise, so this only ever strips an isoform tag.
_ISOFORM_SUFFIX = re.compile(r"-\d+$")


def compound_canonical_key(inchikey: str) -> str:
    """ETL-aligned compound canonical key: 'inchikey:{InChIKey}' (uppercased, stripped)."""
    return f"inchikey:{inchikey.strip().upper()}"


def make_compound_id(inchikey: str) -> str:
    """Deterministic UUID v5 compound id, byte-identical to the ETL pipeline."""
    return str(uuid.uuid5(COMPOUND_NS, compound_canonical_key(inchikey)))


def fold_isoform(accession: str) -> str:
    """Uppercase, strip, and fold a UniProt isoform suffix to its parent accession.

    'P04637-2' -> 'P04637'. Network-level target analysis works at the canonical
    protein, matching ChEMBL / STRING / g:Profiler granularity.
    """
    return _ISOFORM_SUFFIX.sub("", accession.strip().upper())


def target_canonical_key(accession: str | None = None, ensembl: str | None = None,
                         gene: str | None = None) -> str:
    """ETL-aligned target canonical key via the uniprot→ensembl→gene cascade.

    Prefers a UniProt accession (isoform-folded, 'uniprot:{accession}'), then an
    Ensembl gene id ('ensembl:{id}'), then a gene symbol ('gene:{SYMBOL}').
    """
    acc = (accession or "").strip()
    if acc:
        return f"uniprot:{fold_isoform(acc)}"
    ens = (ensembl or "").strip()
    if ens:
        return f"ensembl:{ens}"
    sym = (gene or "").strip()
    if sym:
        return f"gene:{sym.upper()}"
    raise ValueError("target_canonical_key requires uniprot, ensembl, or gene")


def make_target_id(accession: str | None = None, ensembl: str | None = None,
                   gene: str | None = None) -> str:
    """Deterministic UUID v5 target id, byte-identical to the ETL pipeline."""
    return str(uuid.uuid5(TARGET_NS, target_canonical_key(accession, ensembl, gene)))


def make_compound_target_id(compound_id: str, target_id: str) -> str:
    """Deterministic UUID v5 compound-target bridge id (pair grain), byte-identical to ETL."""
    return str(uuid.uuid5(COMPOUND_TARGET_NS, f"{compound_id}:{target_id}"))
