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
    ArriveIn,
    ArriveResult,
    CancelIn,
    CancelPreview,
    CancelResult,
    HandleIn,
    HandleResult,
    MatchDetail,
    MyMatchPage,
    PublishIn,
    RateIn,
    RateResult,
    RecommendPage,
    WithdrawIn,
    WithdrawResult,
)
from tennis_match_api.models import AppUser
from tennis_match_api.response import ApiResponse
from tennis_match_api.services.lifecycle_service import (
    arrive_match,
    cancel_match,
    cancel_preview,
    my_matches,
    rate_match,
)
from tennis_match_api.services.llm.client import LLMClient, get_llm_client
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
    llm: Annotated[LLMClient | None, Depends(get_llm_client)],
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
        llm=llm,
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
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    request_id: Annotated[str, Query(alias="requestId")],
    status: Annotated[Literal["pending", "agreed", "rejected", "cancelled"] | None, Query()] = None,
) -> ApiResponse[ApplicationList]:
    return ApiResponse(
        data=await list_applications(session, user, request_id, status, settings, clock)
    )


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


@router.get("/match/cancel/preview", response_model=ApiResponse[CancelPreview])
async def preview_cancel(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
    request_id: Annotated[str, Query(alias="requestId")],
) -> ApiResponse[CancelPreview]:
    return ApiResponse(data=await cancel_preview(session, user, request_id, clock))


@router.post("/match/cancel", response_model=ApiResponse[CancelResult])
async def cancel(
    payload: CancelIn,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[CancelResult]:
    result = await cancel_match(session, user, payload.request_id, payload.reason, settings, clock)
    return ApiResponse(data=result)


@router.get("/match/my", response_model=ApiResponse[MyMatchPage])
async def my(
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
    kind: Annotated[Literal["all", "published", "applied", "matched"], Query(alias="type")] = "all",
    tab: Annotated[
        Literal["pending", "confirmed", "completed", "cancelled"] | None, Query()
    ] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(alias="pageSize", ge=1, le=50)] = 10,
) -> ApiResponse[MyMatchPage]:
    data = await my_matches(
        session,
        user,
        kind=kind,
        tab=tab,
        page=page,
        page_size=page_size,
        settings=settings,
        clock=clock,
    )
    return ApiResponse(data=data)


@router.post("/match/arrive", response_model=ApiResponse[ArriveResult])
async def arrive(
    payload: ArriveIn,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[ArriveResult]:
    return ApiResponse(data=await arrive_match(session, user, payload.request_id, settings, clock))


@router.post("/match/rate", response_model=ApiResponse[RateResult])
async def rate(
    payload: RateIn,
    user: Annotated[AppUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> ApiResponse[RateResult]:
    pairs = [(item.ratee_id, item.score) for item in payload.ratings]
    return ApiResponse(data=await rate_match(session, user, payload.request_id, pairs, clock))
