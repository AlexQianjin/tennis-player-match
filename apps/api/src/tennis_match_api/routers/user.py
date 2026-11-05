from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.config import Settings, get_settings
from tennis_match_api.deps import get_current_user, get_session
from tennis_match_api.models import AppUser
from tennis_match_api.response import ApiResponse
from tennis_match_api.schemas import Profile, ProfileUpdate, UserPublic
from tennis_match_api.services.profile_service import (
    build_profile,
    get_public_profile,
    parse_public_user_id,
    update_profile,
)

router = APIRouter(prefix="/api/v1", tags=["user"])


@router.get("/user/profile", response_model=ApiResponse[Profile])
async def read_profile(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[Profile]:
    return ApiResponse(data=await build_profile(session, user))


@router.post("/user/profile", response_model=ApiResponse[Profile])
@router.patch("/user/profile", response_model=ApiResponse[Profile])
async def write_profile(
    payload: ProfileUpdate,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[Profile]:
    return ApiResponse(data=await update_profile(session, user, payload, settings, clock))


@router.get("/user/{user_id}/public", response_model=ApiResponse[UserPublic])
async def read_public_profile(
    user_id: str,
    _viewer: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> ApiResponse[UserPublic]:
    return ApiResponse(data=await get_public_profile(session, parse_public_user_id(user_id)))
