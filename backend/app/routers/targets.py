"""Target validation HTTP surface."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.integrations.uniprot import UniProtClient
from app.repositories.target import TargetRepository
from app.schemas.target import ValidateTargetsRequest, ValidateTargetsResponse
from app.services.input_validation import resolve_targets

router = APIRouter(tags=["targets"])


@router.post("/targets/validate", response_model=ValidateTargetsResponse)
async def validate_targets(
    payload: ValidateTargetsRequest, session: AsyncSession = Depends(get_session)
) -> ValidateTargetsResponse:
    async with httpx.AsyncClient() as client:
        resolved, failed = await resolve_targets(
            payload.inputs, TargetRepository(session), UniProtClient(client)
        )
    await session.commit()  # persist validated entities (idempotent)
    return ValidateTargetsResponse(resolved=resolved, failed=failed)
