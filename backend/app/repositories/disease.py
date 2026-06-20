"""Disease data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disease import Disease, DiseaseAlias
from app.services.alias_search import like_escape


class DiseaseRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_all(self) -> list[Disease]:
        result = await self.session.execute(select(Disease).order_by(Disease.disease_name))
        return list(result.scalars().all())

    async def exists(self, disease_id: uuid.UUID) -> bool:
        result = await self.session.execute(
            select(Disease.disease_id).where(Disease.disease_id == disease_id)
        )
        return result.first() is not None

    async def search_candidates(self, q: str) -> list[tuple[Disease, str | None]]:
        """Return raw candidate (disease, matched_alias | None) rows for ranking.

        ``q`` is already stripped by the caller.  Empty ``q`` returns all diseases
        ordered by disease name, each paired with ``None``.  Non-empty ``q``
        executes two queries:
        - disease_name ILIKE %q% (alias=None)
        - alias_name ILIKE %q% (alias=alias_name)
        and merges them in Python (data set is small: ~10 diseases / ~50 aliases).
        Uses SQLAlchemy ``.ilike()`` with a bound pattern — never string-formats ``q``.
        The term's ``%``/``_`` are escaped (``like_escape``) so they match literally
        instead of acting as LIKE wildcards.
        """
        if not q:
            rows = await self.session.execute(select(Disease).order_by(Disease.disease_name))
            return [(d, None) for d in rows.scalars().all()]

        pattern = f"%{like_escape(q)}%"

        # Canonical-name hits
        canon_result = await self.session.execute(
            select(Disease).where(Disease.disease_name.ilike(pattern, escape="\\"))
        )
        canon_rows: list[tuple[Disease, str | None]] = [
            (d, None) for d in canon_result.scalars().all()
        ]

        # Alias-name hits (join alias table to the parent disease)
        alias_result = await self.session.execute(
            select(Disease, DiseaseAlias.alias_name)
            .join(DiseaseAlias, DiseaseAlias.disease_id == Disease.disease_id)
            .where(DiseaseAlias.alias_name.ilike(pattern, escape="\\"))
        )
        alias_rows: list[tuple[Disease, str | None]] = [
            (disease, alias_name) for disease, alias_name in alias_result.all()
        ]

        return canon_rows + alias_rows
