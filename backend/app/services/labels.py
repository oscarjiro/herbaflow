"""Display-label resolution (single home).

A run stores only ids (``plant_ids`` / ``disease_id``); the human-readable name is
catalog data. This is the one place that turns those ids into display name(s), shared by
analysis-create (which stores the resolved names on the run so the frontend never needs a
second catalog fetch to name the subject) and export (which falls back to it when a run has
no stored ``labels``). Display-only (B4); never used for identity.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable

from app.repositories.disease import DiseaseRepository
from app.repositories.plant import PlantRepository


async def resolve_entity_labels(
    plant_repo: PlantRepository,
    disease_repo: DiseaseRepository,
    plant_ids: Iterable[uuid.UUID | str] | None,
    disease_id: uuid.UUID | None,
) -> dict[str, str | None]:
    """Resolve display name(s) for a run's selected plant(s) and disease from the catalog.

    Returns ``{"plant": <names joined on ", " or None>, "disease": <name or None>}``.
    Multiple plants join in catalog order (matching the run header). Ids with no catalog
    row yield ``None`` (a manual/absent side is expected to be ``None`` so callers print
    N/A). Pass ``None`` for a side that should be skipped (e.g. already stored, or manual).
    """
    wanted = {str(p) for p in (plant_ids or [])}
    plant: str | None = None
    if wanted:
        plants = await plant_repo.list_all()
        names = [
            p.canonical_scientific_name
            for p in plants
            if str(p.plant_id) in wanted and p.canonical_scientific_name
        ]
        plant = ", ".join(names) if names else None

    disease: str | None = None
    if disease_id is not None:
        diseases = await disease_repo.list_all()
        disease = next(
            (d.disease_name for d in diseases if d.disease_id == disease_id),
            None,
        )

    return {"plant": plant, "disease": disease}
