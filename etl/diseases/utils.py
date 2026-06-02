"""diseases ETL helpers — thin re-export over shared.

Identity, text, and frame I/O all live in shared modules now; this file only
binds the names the diseases steps import and the disease-specific canonical_key.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # etl/

from shared.utils import safe_str, clean_str, normalize_text  # noqa: F401
from shared.frames import read_frame, write_frame, validate_required_columns  # noqa: F401
from shared.identity import (  # noqa: F401
    DISEASE_NS,
    DISEASE_ALIAS_NS,
    disease_canonical_key,
    disease_id,
    disease_alias_id,
    slugify,
    ALIAS_PRIORITY,
    pick_alias,
)

# Disease canonical key == the shared slug (single source of truth).
canonical_key = slugify
make_slug_key = slugify  # backward-compatible alias for any lingering caller

# Convenience path re-used by step 01 and 02 as their default settings path.
SETTINGS_PATH: Path = Path(__file__).resolve().parent / "settings.yml"
