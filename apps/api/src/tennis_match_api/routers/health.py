from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.deps import get_session
from tennis_match_api.response import ApiResponse
from tennis_match_api.schemas import HealthData

router = APIRouter(tags=["health"])


@router.get("/healthz", response_model=ApiResponse[HealthData])
@router.get("/api/v1/health", response_model=ApiResponse[HealthData])
async def health() -> ApiResponse[HealthData]:
    return ApiResponse(data=HealthData(status="ok"))


@router.get("/api/v1/health/db", response_model=ApiResponse[HealthData])
async def health_db(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[HealthData]:
    await session.execute(text("SELECT 1"))
    return ApiResponse(data=HealthData(status="ok"))
