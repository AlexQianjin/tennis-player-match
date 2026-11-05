from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.config import Settings, get_settings
from tennis_match_api.deps import get_current_user, get_session
from tennis_match_api.errors import BizError
from tennis_match_api.match_schemas import (
    ApplicationList,
    ApplyIn,
    ApplyResult,
    HandleIn,
    HandleResult,
    MatchDetail,
    PublishIn,
    RecommendPage,
    WithdrawIn,
    WithdrawResult,
)
from tennis_match_api.models import AppUser
from tennis_match_api.response import ApiResponse
from tennis_match_api.services.match_service import (
    apply_to_match,
    handle_application,
    list_applications,
    match_detail,
    publish_match,
    recommend_matches,
    withdraw_application,
)

router = APIRouter(prefix="/api/v1", tags=["match"])


@router.post("/match/publish", response_model=ApiResponse[MatchDetail])
async def publish(
    payload: PublishIn,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[MatchDetail]:
    detail = await publish_match(
        session,
        user,
        match_date=payload.date,
        time_slot=payload.time_slot,
        court_id=payload.court_id,
        match_type=payload.match_type,
        slots_needed=payload.slots_needed,
        expected_ntrp_min=payload.expected_ntrp_min,
        expected_ntrp_max=payload.expected_ntrp_max,
        gender_pref=payload.gender_pref,
        settings=settings,
        clock=clock,
    )
    return ApiResponse(data=detail)


@router.get("/match/recommend", response_model=ApiResponse[RecommendPage])
async def recommend(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    city: Annotated[str, Query()],
    ntrp_min: Annotated[float | None, Query(alias="ntrpMin")] = None,
    ntrp_max: Annotated[float | None, Query(alias="ntrpMax")] = None,
    gender: Annotated[Literal["male", "female"] | None, Query()] = None,
    match_date: Annotated[date | None, Query(alias="date")] = None,
    time_slot: Annotated[str | None, Query(alias="timeSlot")] = None,
    court_id: Annotated[str | None, Query(alias="courtId")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=50)] = 10,
) -> ApiResponse[RecommendPage]:
    page_data = await recommend_matches(
        session,
        user,
        city=city,
        ntrp_min=ntrp_min,
        ntrp_max=ntrp_max,
        gender=gender,
        match_date=match_date,
        time_slot=time_slot,
        court_id=court_id,
        page=page,
        page_size=page_size,
        settings=settings,
        clock=clock,
    )
    return ApiResponse(data=page_data)


@router.get("/match/detail/{request_id}", response_model=ApiResponse[MatchDetail])
async def detail(
    request_id: str,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[MatchDetail]:
    if not request_id.isdigit():
        raise BizError(404, "资源不存在")
    data = await match_detail(session, user, int(request_id), settings, clock)
    return ApiResponse(data=data)


@router.post("/match/apply", response_model=ApiResponse[ApplyResult])
async def apply(
    payload: ApplyIn,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[ApplyResult]:
    return ApiResponse(
        data=await apply_to_match(session, user, payload.request_id, settings, clock)
    )


@router.post("/match/application/withdraw", response_model=ApiResponse[WithdrawResult])
async def withdraw(
    payload: WithdrawIn,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[WithdrawResult]:
    return ApiResponse(
        data=await withdraw_application(session, user, payload.application_id, settings, clock)
    )


@router.get("/match/applications", response_model=ApiResponse[ApplicationList])
async def applications(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    request_id: Annotated[str, Query(alias="requestId")],
    status: Annotated[Literal["pending", "agreed", "rejected", "cancelled"] | None, Query()] = None,
) -> ApiResponse[ApplicationList]:
    return ApiResponse(data=await list_applications(session, user, request_id, status))


@router.post("/match/handle", response_model=ApiResponse[HandleResult])
async def handle(
    payload: HandleIn,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[HandleResult]:
    result = await handle_application(
        session,
        user,
        payload.application_id,
        payload.action,
        settings,
        clock,
    )
    return ApiResponse(data=result)
