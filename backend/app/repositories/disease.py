"""Disease data access."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disease import Disease
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
        """Return raw candidate (disease, None) rows for ranking.

        ``q`` is already stripped by the caller. Empty ``q`` returns all diseases ordered by
        disease name. Non-empty ``q`` matches the disease name (ILIKE %q%); synonym/alias search
        was retired with the alias tables (the frontend filters a locally cached catalog, so
        ``matched_alias`` is always ``None``). Uses a bound ``.ilike()`` pattern — never
        string-formats ``q`` — with the term's ``%``/``_`` escaped (``like_escape``).
        """
        if not q:
            rows = await self.session.execute(select(Disease).order_by(Disease.disease_name))
            return [(d, None) for d in rows.scalars().all()]

        pattern = f"%{like_escape(q)}%"
        canon_result = await self.session.execute(
            select(Disease).where(Disease.disease_name.ilike(pattern, escape="\\"))
        )
        return [(d, None) for d in canon_result.scalars().all()]
