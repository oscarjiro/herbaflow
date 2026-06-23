"""Disease read service."""

from __future__ import annotations

import logging
import uuid
from collections.abc import Hashable

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.disease import Disease
from app.repositories.disease import DiseaseRepository
from app.repositories.disease_target import DiseaseTargetRepository
from app.schemas.disease import DiseaseRead
from app.services.alias_search import merge_candidates, rank_match

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

        if not term:
            # Empty query: rows already ordered by disease name; just page.
            paged = rows[offset : offset + limit]
            reads = [
                (DiseaseRead.model_validate(disease), disease.disease_id) for disease, _ in paged
            ]
        else:
            # Build flat candidate list: (disease_id, rank, matched_alias | None)
            candidates: list[tuple[Hashable, int, str | None]] = []
            for disease, alias in rows:
                r = rank_match(term, canonical=disease.disease_name)
                if r is not None:
                    candidates.append((disease.disease_id, r, None))
                    continue
                r = rank_match(term, alias=alias)
                if r is not None:
                    candidates.append((disease.disease_id, r, alias))

            merged = merge_candidates(candidates)

            # Map back to Disease objects; tie-break within same rank by disease name.
            disease_by_id: dict[uuid.UUID, Disease] = {
                disease.disease_id: disease for disease, _ in rows
            }

            def sort_key(row: tuple[Hashable, int, str | None]) -> tuple[int, str]:
                key, rank, _alias = row
                disease = disease_by_id[key]  # type: ignore[index]
                name = (disease.disease_name or "").lower()
                return (rank, name)

            merged.sort(key=sort_key)
            page: list[tuple[Hashable, int, str | None]] = merged[offset : offset + limit]

            reads = []
            for disease_id, _rank, matched_alias in page:
                disease = disease_by_id[disease_id]  # type: ignore[index]
                read = DiseaseRead.model_validate(disease)
                read.matched_alias = matched_alias
                reads.append((read, disease.disease_id))

        counts = await self.target_repo.target_counts([did for _, did in reads])
        for read, did in reads:
            read.target_count = counts.get(did, 0)
        result = [read for read, _ in reads]
        logger.info("disease search q=%r count=%d", q, len(result))
        return result
