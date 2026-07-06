"""Disease read service."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.disease import DiseaseRepository
from app.repositories.disease_target import DiseaseTargetRepository
from app.schemas.disease import DiseaseRead
from app.services.alias_search import rank_and_page_search

logger = logging.getLogger("herbaflow.diseases")


class DiseaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = DiseaseRepository(session)
        self.target_repo = DiseaseTargetRepository(session)

    async def list_all(self) -> list[DiseaseRead]:
        rows = await self.repo.list_all()
        return [DiseaseRead.model_validate(r) for r in rows]

    async def search(
        self,
        q: str | None,
        *,
        limit: int,
        offset: int,
    ) -> list[DiseaseRead]:
        """Search diseases by canonical name or alias, ranked and paged.

        Empty/absent ``q`` returns the full list ordered by disease name.
        An unknown term returns an empty list (200 []).
        """
        term = (q or "").strip().lower()
        rows = await self.repo.search_candidates(q=term)

        ranked = rank_and_page_search(
            rows,
            term,
            name_of=lambda disease: disease.disease_name,
            id_of=lambda disease: disease.disease_id,
            limit=limit,
            offset=offset,
        )
        reads = []
        for disease, matched_alias in ranked:
            read = DiseaseRead.model_validate(disease)
            read.matched_alias = matched_alias
            reads.append((read, disease.disease_id))

        counts = await self.target_repo.target_counts([did for _, did in reads])
        for read, did in reads:
            read.target_count = counts.get(did, 0)
        result = [read for read, _ in reads]
        logger.info("disease search q=%r count=%d", q, len(result))
        return result
