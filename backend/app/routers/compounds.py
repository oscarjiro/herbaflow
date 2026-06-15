"""Compound validation HTTP surface."""

from __future__ import annotations

import httpx
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.integrations.pubchem import PubChemClient
from app.repositories.compound import CompoundRepository
from app.schemas.compound import ValidateRequest, ValidateResponse
from app.security import RATE_LIMIT_VALIDATE, limiter
from app.services.input_validation import resolve_compounds

router = APIRouter(tags=["compounds"])


@router.post("/compounds/validate", response_model=ValidateResponse)
@limiter.limit(RATE_LIMIT_VALIDATE)
async def validate_compounds(
    request: Request,
    payload: ValidateRequest,
    session: AsyncSession = Depends(get_session),
) -> ValidateResponse:
    async with httpx.AsyncClient() as client:
        resolved, failed = await resolve_compounds(
            payload.inputs, CompoundRepository(session), PubChemClient(client)
        )
    await session.commit()  # persist validated entities (idempotent)
    return ValidateResponse(resolved=resolved, failed=failed)
