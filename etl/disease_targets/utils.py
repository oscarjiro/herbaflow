"""disease_targets ETL helpers — thin re-export over shared + target canonical key."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/

from shared.frames import read_frame, validate_required_columns, write_frame  # noqa: F401
from shared.identity import (  # noqa: F401
    DISEASE_TARGET_NS,
    TARGET_ALIAS_NS,
    TARGET_NS,
    disease_target_id,
    fold_isoform,
    slugify,
    target_alias_id,
    target_canonical_key,
    target_id,
    target_id_from_key,
)
from shared.utils import clean_str, normalize_text, safe_str  # noqa: F401

make_slug_key = slugify  # backward-compatible alias


def canonical_key_for_target(uniprot_accession: str | None, ensembl_id: str) -> str:
    """canonical_key: 'uniprot:{folded acc}' if available, else 'ensembl:{id}'."""
    return target_canonical_key(uniprot=uniprot_accession, ensembl=ensembl_id)
