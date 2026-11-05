from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.deps import get_identity, get_session
from tennis_match_api.identity import WxIdentity
from tennis_match_api.response import ApiResponse
from tennis_match_api.schemas import LoginResult
from tennis_match_api.services.auth_service import login_user

router = APIRouter(prefix="/api/v1", tags=["auth"])


@router.post("/auth/login", response_model=ApiResponse[LoginResult])
async def login(
    identity: Annotated[WxIdentity, Depends(get_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[LoginResult]:
    return ApiResponse(data=await login_user(session, identity, clock))
