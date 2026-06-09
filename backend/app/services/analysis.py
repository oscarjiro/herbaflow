"""Analysis run service: validate, create, fetch, advance."""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app import contracts
from app.clock import now_utc
from app.errors import GoneProblem, NotFoundProblem, ValidationProblem
from app.pipeline import engine
from app.pipeline.limits import EntityCapExceeded, check_entity_cap
from app.repositories.analysis import AnalysisRepository
from app.repositories.compound import CompoundRepository
from app.repositories.disease import DiseaseRepository
from app.repositories.plant import PlantRepository
from app.schemas.analysis import AnalysisCreate, AnalysisRead

logger = logging.getLogger("herbaflow.analysis")


class AnalysisService:
    def __init__(
        self,
        *,
        plant_repo: Any,
        disease_repo: Any,
        analysis_repo: Any,
        compound_repo: Any,
    ) -> None:
        self.plant_repo = plant_repo
        self.disease_repo = disease_repo
        self.analysis_repo = analysis_repo
        self.compound_repo = compound_repo

    @classmethod
    def from_session(cls, session: AsyncSession) -> AnalysisService:
        return cls(
            plant_repo=PlantRepository(session),
            disease_repo=DiseaseRepository(session),
            analysis_repo=AnalysisRepository(session),
            compound_repo=CompoundRepository(session),
        )

    async def create(self, payload: AnalysisCreate) -> AnalysisRead:
        logger.info(
            "creating analysis: %d plant(s), disease %s, %d manual compound(s), mode=%s",
            len(payload.plant_ids),
            str(payload.disease_id)[:8],
            len(payload.manual_compound_ids),
            payload.mode.value,
        )
        missing = await self.plant_repo.missing_ids(payload.plant_ids)
        if missing:
            raise ValidationProblem(
                detail="Unknown plant ids.", invalid_plant_ids=[str(p) for p in missing]
            )
        if not await self.disease_repo.exists(payload.disease_id):
            raise ValidationProblem(
                detail="Unknown disease id.", invalid_disease_id=str(payload.disease_id)
            )
        if payload.manual_compound_ids:
            try:
                check_entity_cap("compound", current=0, adding=len(payload.manual_compound_ids))
            except EntityCapExceeded as e:
                raise ValidationProblem(
                    detail=f"Too many manual compounds (max {e.cap}, got {e.adding})."
                ) from e
            existing = await self.compound_repo.existing_ids(payload.manual_compound_ids)
            missing = [c for c in payload.manual_compound_ids if c not in existing]
            if missing:
                raise ValidationProblem(
                    detail="Unknown compound ids.",
                    invalid_compound_ids=[str(c) for c in missing],
                )
        pipeline_parameters = {"adme": contracts.adme_defaults()}
        run = await self.analysis_repo.create(
            analysis_name=payload.analysis_name,
            disease_id=payload.disease_id,
            plant_ids=payload.plant_ids,
            mode=payload.mode.value,
            manual_compound_ids=payload.manual_compound_ids,
            pipeline_parameters=pipeline_parameters,
        )
        return AnalysisRead.model_validate(run)

    async def get(self, analysis_id: uuid.UUID) -> AnalysisRead:
        run = await self.analysis_repo.get(analysis_id)
        if run is None:
            raise NotFoundProblem(detail="Analysis run not found.")
        if run.expires_at is not None and run.expires_at < now_utc():
            raise GoneProblem(detail="Analysis run has expired.")
        return AnalysisRead.model_validate(run)

    async def advance(self, analysis_id: uuid.UUID) -> None:
        await engine.advance_run(self.analysis_repo, analysis_id)
