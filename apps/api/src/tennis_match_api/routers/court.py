from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.deps import get_session
from tennis_match_api.models import Court
from tennis_match_api.response import ApiResponse
from tennis_match_api.schemas import CourtList, CourtOut

router = APIRouter(prefix="/api/v1", tags=["court"])


@router.get("/courts", response_model=ApiResponse[CourtList])
async def list_courts(
    session: Annotated[AsyncSession, Depends(get_session)],
    city: Annotated[str, Query()] = "武汉",
) -> ApiResponse[CourtList]:
    rows = (
        await session.scalars(
            select(Court)
            .where(Court.city == city, Court.is_active.is_(True), Court.is_deleted.is_(False))
            .order_by(Court.sort_order, Court.id)
        )
    ).all()
    items = [
        CourtOut(
            id=str(row.id),
            name=row.name,
            district=row.district,
            address=row.address,
            latitude=float(row.latitude) if row.latitude is not None else None,
            longitude=float(row.longitude) if row.longitude is not None else None,
        )
        for row in rows
    ]
    return ApiResponse(data=CourtList(items=items))
