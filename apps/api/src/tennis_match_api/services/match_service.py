"""Publish, recommend (rules only), detail, apply, withdraw, and handle.

Cancel, leave, arrive, rate, and the scheduler stay in M3. LLM scores stay null.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock
from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError
from tennis_match_api.match_schemas import (
    ApplicationItem,
    ApplicationList,
    ApplyResult,
    ArriveWindow,
    HandleResult,
    MatchDetail,
    MatchSummary,
    ParticipantOut,
    RecommendItem,
    RecommendPage,
    UserBrief,
    WithdrawResult,
)
from tennis_match_api.models import (
    Application,
    AppUser,
    Court,
    MatchParticipant,
    MatchRating,
    MatchRequest,
)
from tennis_match_api.ntrp import parse_ntrp
from tennis_match_api.services.profile_service import ensure_profile_completed, public_from_user
from tennis_match_api.services.ranking import credit_norm, ntrp_closeness, rule_score
from tennis_match_api.services.state_machine import (
    ConcurrencyConflict,
    available_actions,
    record_transition,
    retry_on_conflict,
)
from tennis_match_api.timefmt import format_shanghai

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_SLOT = re.compile(r"^((?:[01]\d|2[0-3]):[0-5]\d)-((?:[01]\d|2[0-3]):[0-5]\d)$")
_STATUS = {1: "pending", 2: "matched", 3: "completed", 4: "cancelled"}
_APP_STATUS = {1: "pending", 2: "agreed", 3: "rejected", 4: "cancelled"}
_TYPE = {1: "singles", 2: "doubles"}
_TYPE_CODE = {"singles": 1, "doubles": 2}
_GENDER = {1: "male", 2: "female"}
_GENDER_CODE = {"male": 1, "female": 2}
_PREF = {0: "any", 1: "male", 2: "female"}
_PREF_CODE = {"any": 0, "male": 1, "female": 2}
_FULL = "该约球已满员"
_CONFLICT = "状态已变化，请刷新后重试"
_ACTIVE = "您已有一个进行中的约球，请先完成或取消"
_DUP = "您已申请过该约球"


def raise_for_integrity(exc: IntegrityError) -> None:
    message = str(getattr(exc, "orig", exc))
    if "uq_mr_one_active_per_publisher" in message:
        raise BizError(40901, _ACTIVE) from exc
    if "uq_application_req_applicant" in message:
        raise BizError(40902, _DUP) from exc
    raise exc


async def publish_match(
    session: AsyncSession,
    user: AppUser,
    *,
    match_date: date,
    time_slot: str,
    court_id: str,
    match_type: str,
    slots_needed: int | None,
    expected_ntrp_min: float | None,
    expected_ntrp_max: float | None,
    gender_pref: str,
    settings: Settings,
    clock: Clock,
) -> MatchDetail:
    ensure_profile_completed(user)
    if user.ntrp is None:
        raise BizError(40001, "资料未完善，请先完善资料")
    start_at, end_at = _schedule(match_date, time_slot, clock.now())
    slots = _slots(match_type, slots_needed)
    low, high = _narrow_expected(
        user.ntrp, expected_ntrp_min, expected_ntrp_max, settings.ntrp_hard_diff
    )
    court = await _court_for_user(session, court_id, user.city or "")
    active = await session.scalar(
        select(MatchRequest.id).where(
            MatchRequest.publisher_id == user.id,
            MatchRequest.status.in_((1, 2)),
            MatchRequest.is_deleted.is_(False),
        )
    )
    if active is not None:
        raise BizError(40901, _ACTIVE)
    now = clock.now()
    request = MatchRequest(
        publisher_id=user.id,
        court_id=court.id,
        city=court.city,
        match_date=match_date,
        time_slot=time_slot,
        start_at=start_at,
        end_at=end_at,
        match_type=_TYPE_CODE[match_type],
        slots_needed=slots,
        filled_count=0,
        expected_ntrp_min=low,
        expected_ntrp_max=high,
        gender_pref=_PREF_CODE[gender_pref],
        status=1,
        version=0,
        is_deleted=False,
    )
    session.add(request)
    try:
        await session.flush()
        session.add(
            MatchParticipant(
                request_id=request.id,
                user_id=user.id,
                role=1,
                application_id=None,
                status=1,
                arrived=False,
                arrived_time=None,
                rated=False,
                rated_time=None,
                left_time=None,
                version=0,
            )
        )
        record_transition(
            session,
            entity_type="match_request",
            entity_id=int(request.id),
            request_id=int(request.id),
            action="publish",
            from_status=None,
            to_status=1,
            operator_id=int(user.id),
            at=now,
        )
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise_for_integrity(exc)
    return await match_detail(session, user, int(request.id), settings, clock)


@retry_on_conflict
async def apply_to_match(
    session: AsyncSession,
    user: AppUser,
    request_id: str,
    settings: Settings,
    clock: Clock,
) -> ApplyResult:
    await session.refresh(user)
    ensure_profile_completed(user)
    request = await _request(session, request_id)
    now = clock.now()
    _require_joinable(request, now)
    if request.publisher_id == user.id:
        raise BizError(40304, "不能申请自己发布的约球")
    publisher = await session.get(AppUser, request.publisher_id)
    if publisher is None:
        raise BizError(404, "资源不存在")
    _require_compatible(user, publisher, request, settings)
    existing = await session.scalar(
        select(Application.id).where(
            Application.request_id == request.id,
            Application.applicant_id == user.id,
        )
    )
    if existing is not None:
        raise BizError(40902, _DUP)
    application = Application(
        request_id=request.id,
        applicant_id=user.id,
        status=1,
        close_reason=None,
        handle_time=None,
        version=0,
        create_time=now,
    )
    session.add(application)
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise_for_integrity(exc)
    await _bump(session, request)
    record_transition(
        session,
        entity_type="application",
        entity_id=int(application.id),
        request_id=int(request.id),
        action="apply",
        from_status=None,
        to_status=1,
        operator_id=int(user.id),
        at=now,
    )
    await session.commit()
    summary = await _summary_for(session, user, int(request.id), settings, clock)
    return ApplyResult(application_id=str(application.id), status="pending", request=summary)


@retry_on_conflict
async def withdraw_application(
    session: AsyncSession,
    user: AppUser,
    application_id: str,
    settings: Settings,
    clock: Clock,
) -> WithdrawResult:
    await session.refresh(user)
    application = await _application(session, application_id)
    if application.applicant_id != user.id:
        raise BizError(403, "无权限")
    request = await _request(session, str(application.request_id))
    if application.status != 1 or request.status != 1:
        raise BizError(40904, _CONFLICT)
    now = clock.now()
    changed = await session.execute(
        update(Application)
        .where(
            Application.id == application.id,
            Application.status == 1,
            Application.version == application.version,
        )
        .values(status=4, close_reason=3, handle_time=now, version=application.version + 1)
    )
    if changed.rowcount != 1:
        raise ConcurrencyConflict()
    await _bump(session, request)
    record_transition(
        session,
        entity_type="application",
        entity_id=int(application.id),
        request_id=int(request.id),
        action="withdraw",
        from_status=1,
        to_status=4,
        operator_id=int(user.id),
        at=now,
    )
    await session.commit()
    return WithdrawResult(status="cancelled")


@retry_on_conflict
async def handle_application(
    session: AsyncSession,
    user: AppUser,
    application_id: str,
    action: str,
    settings: Settings,
    clock: Clock,
) -> HandleResult:
    await session.refresh(user)
    application = await _application(session, application_id)
    request = await _request(session, str(application.request_id))
    if request.publisher_id != user.id:
        raise BizError(403, "无权限")
    now = clock.now()
    if request.status in (2, 3) or request.filled_count >= request.slots_needed:
        raise BizError(40903, _FULL)
    if request.status != 1 or request.start_at <= now:
        raise BizError(40904, _CONFLICT)
    if application.status != 1:
        raise BizError(40904, _CONFLICT)
    if action == "reject":
        await _close_application(
            session,
            application,
            status=3,
            close_reason=1,
            action="reject",
            now=now,
            operator_id=int(user.id),
        )
        await _bump(session, request)
        record_transition(
            session,
            entity_type="match_request",
            entity_id=int(request.id),
            request_id=int(request.id),
            action="reject",
            from_status=1,
            to_status=1,
            operator_id=int(user.id),
            at=now,
        )
        await session.commit()
        summary = await _summary_for(session, user, int(request.id), settings, clock)
        return HandleResult(application_status="rejected", request=summary)

    will_fill = request.filled_count + 1 >= request.slots_needed
    await _close_application(
        session,
        application,
        status=2,
        close_reason=None,
        action="agree",
        now=now,
        operator_id=int(user.id),
    )
    session.add(
        MatchParticipant(
            request_id=request.id,
            user_id=application.applicant_id,
            role=2,
            application_id=application.id,
            status=1,
            arrived=False,
            arrived_time=None,
            rated=False,
            rated_time=None,
            left_time=None,
            version=0,
        )
    )
    await _bump(
        session,
        request,
        filled_count=request.filled_count + 1,
        status=2 if will_fill else 1,
        matched_time=now if will_fill else None,
        guard_capacity=True,
    )
    record_transition(
        session,
        entity_type="match_request",
        entity_id=int(request.id),
        request_id=int(request.id),
        action="agree",
        from_status=1,
        to_status=2 if will_fill else 1,
        operator_id=int(user.id),
        at=now,
        detail={"filledCount": request.filled_count + 1},
    )
    if will_fill:
        await _reject_remaining(
            session, request, keep_id=int(application.id), now=now, operator_id=int(user.id)
        )
    await session.commit()
    summary = await _summary_for(session, user, int(request.id), settings, clock)
    return HandleResult(application_status="agreed", request=summary)


async def match_detail(
    session: AsyncSession,
    user: AppUser,
    request_id: int,
    settings: Settings,
    clock: Clock,
) -> MatchDetail:
    request = await session.get(MatchRequest, request_id)
    if request is None or request.is_deleted:
        raise BizError(404, "资源不存在")
    summary, publisher, _court = await _load_summary(session, user, request, settings, clock)
    data = summary.model_dump()
    data.pop("publisher")
    participants = await _participants(session, request.id)
    pending: int | None = None
    if request.publisher_id == user.id:
        pending = int(
            await session.scalar(
                select(func.count())
                .select_from(Application)
                .where(Application.request_id == request.id, Application.status == 1)
            )
            or 0
        )
    window_end = request.start_at + timedelta(hours=settings.auto_cancel_hours)
    return MatchDetail(
        **data,
        publisher=public_from_user(publisher),
        participants=participants,
        pending_application_count=pending,
        my_ratings=await _my_ratings(session, request.id, user.id),
        cancel_reason=request.cancel_reason,
        matched_time=None
        if request.matched_time is None
        else format_shanghai(request.matched_time),
        completed_time=None
        if request.completed_time is None
        else format_shanghai(request.completed_time),
        arrive_window=ArriveWindow.model_validate(
            {"from": format_shanghai(request.start_at), "to": format_shanghai(window_end)}
        ),
    )


async def recommend_matches(
    session: AsyncSession,
    user: AppUser,
    *,
    city: str,
    ntrp_min: float | None,
    ntrp_max: float | None,
    gender: str | None,
    match_date: date | None,
    time_slot: str | None,
    court_id: str | None,
    page: int,
    page_size: int,
    settings: Settings,
    clock: Clock,
) -> RecommendPage:
    ensure_profile_completed(user)
    if user.ntrp is None or user.gender is None:
        raise BizError(40001, "资料未完善，请先完善资料")
    low = parse_ntrp(ntrp_min) if ntrp_min is not None else None
    high = parse_ntrp(ntrp_max) if ntrp_max is not None else None
    court_pk = _optional_id(court_id, code=40003, message="球场不存在或不在当前城市")
    now = clock.now()
    hard = settings.ntrp_hard_diff
    stmt = (
        select(MatchRequest, AppUser, Court)
        .join(AppUser, AppUser.id == MatchRequest.publisher_id)
        .join(Court, Court.id == MatchRequest.court_id)
        .where(
            MatchRequest.city == city,
            MatchRequest.status == 1,
            MatchRequest.is_deleted.is_(False),
            MatchRequest.start_at > now,
            MatchRequest.filled_count < MatchRequest.slots_needed,
            MatchRequest.publisher_id != user.id,
            AppUser.is_deleted.is_(False),
            func.abs(AppUser.ntrp - user.ntrp) <= hard,
            (MatchRequest.expected_ntrp_min.is_(None))
            | (MatchRequest.expected_ntrp_min <= user.ntrp),
            (MatchRequest.expected_ntrp_max.is_(None))
            | (MatchRequest.expected_ntrp_max >= user.ntrp),
            (MatchRequest.gender_pref == 0) | (MatchRequest.gender_pref == user.gender),
            ~select(Application.id)
            .where(
                Application.request_id == MatchRequest.id,
                Application.applicant_id == user.id,
                Application.status.in_((3, 4)),
            )
            .exists(),
            ~select(MatchParticipant.id)
            .where(
                MatchParticipant.request_id == MatchRequest.id,
                MatchParticipant.user_id == user.id,
            )
            .exists(),
        )
        .order_by(MatchRequest.start_at, MatchRequest.id)
        .limit(settings.recommend_candidate_cap)
    )
    if low is not None:
        stmt = stmt.where(AppUser.ntrp >= low)
    if high is not None:
        stmt = stmt.where(AppUser.ntrp <= high)
    if gender is not None:
        stmt = stmt.where(AppUser.gender == _GENDER_CODE[gender])
    if match_date is not None:
        stmt = stmt.where(MatchRequest.match_date == match_date)
    if time_slot is not None:
        stmt = stmt.where(MatchRequest.time_slot == time_slot)
    if court_pk is not None:
        stmt = stmt.where(MatchRequest.court_id == court_pk)
    rows = (await session.execute(stmt)).all()
    scored: list[tuple[float, datetime, int, MatchRequest, AppUser, Court]] = []
    for request, publisher, court in rows:
        if publisher.ntrp is None:
            continue
        score = rule_score(
            credit_norm(int(publisher.credit_score or 0), settings.credit_norm_cap),
            ntrp_closeness(publisher.ntrp, user.ntrp, hard),
            weight_credit=settings.rank_weight_credit,
            weight_ntrp=settings.rank_weight_ntrp,
        )
        scored.append((score, request.start_at, int(request.id), request, publisher, court))
    scored.sort(key=lambda item: (-item[0], item[1], item[2]))
    total = len(scored)
    start = (page - 1) * page_size
    page_rows = scored[start : start + page_size]
    ids = [row[2] for row in page_rows]
    applications = await _applications_for(session, user.id, ids)
    participants = await _participant_roles(session, user.id, ids)
    items: list[RecommendItem] = []
    for score, _, _, request, publisher, court in page_rows:
        summary = _to_summary(
            request,
            publisher,
            court,
            user,
            applications.get(int(request.id)),
            participants.get(int(request.id)),
            clock.now(),
            settings,
        )
        items.append(
            RecommendItem(
                **summary.model_dump(),
                rule_score=round(score, 4),
                llm_score=None,
                final_score=None,
                match_reason=None,
            )
        )
    return RecommendPage(
        items=items,
        page=page,
        page_size=page_size,
        total=total,
        has_more=start + len(items) < total,
        llm_applied=False,
    )


async def list_applications(
    session: AsyncSession,
    user: AppUser,
    request_id: str,
    status: str | None,
) -> ApplicationList:
    request = await _request(session, request_id)
    if request.publisher_id != user.id:
        raise BizError(403, "无权限")
    stmt = (
        select(Application, AppUser)
        .join(AppUser, AppUser.id == Application.applicant_id)
        .where(Application.request_id == request.id)
        .order_by(Application.create_time, Application.id)
    )
    if status is not None:
        code = {name: number for number, name in _APP_STATUS.items()}[status]
        stmt = stmt.where(Application.status == code)
    rows = (await session.execute(stmt)).all()
    items = [
        ApplicationItem(
            application_id=str(application.id),
            applicant=public_from_user(applicant),
            status=_APP_STATUS[application.status],  # type: ignore[arg-type]
            apply_time=format_shanghai(application.create_time),
            llm_score=None,
            match_reason=None,
        )
        for application, applicant in rows
    ]
    return ApplicationList(items=items)


async def _summary_for(
    session: AsyncSession,
    user: AppUser,
    request_id: int,
    settings: Settings,
    clock: Clock,
) -> MatchSummary:
    request = await session.get(MatchRequest, request_id)
    if request is None or request.is_deleted:
        raise BizError(404, "资源不存在")
    summary, _, _ = await _load_summary(session, user, request, settings, clock)
    return summary


async def _load_summary(
    session: AsyncSession,
    user: AppUser,
    request: MatchRequest,
    settings: Settings,
    clock: Clock,
) -> tuple[MatchSummary, AppUser, Court]:
    await session.refresh(request)
    publisher = await session.get(AppUser, request.publisher_id)
    court = await session.get(Court, request.court_id)
    if publisher is None or court is None:
        raise BizError(404, "资源不存在")
    application = await session.scalar(
        select(Application).where(
            Application.request_id == request.id,
            Application.applicant_id == user.id,
        )
    )
    participant = await session.scalar(
        select(MatchParticipant).where(
            MatchParticipant.request_id == request.id,
            MatchParticipant.user_id == user.id,
        )
    )
    summary = _to_summary(
        request, publisher, court, user, application, participant, clock.now(), settings
    )
    return summary, publisher, court


def _to_summary(
    request: MatchRequest,
    publisher: AppUser,
    court: Court,
    viewer: AppUser,
    application: Application | None,
    participant: MatchParticipant | None,
    now: datetime,
    settings: Settings,
) -> MatchSummary:
    role = _role(request, viewer.id, application, participant)
    app_status = None if application is None else _APP_STATUS[application.status]
    window_end = request.start_at + timedelta(hours=settings.auto_cancel_hours)
    actions = available_actions(
        status=request.status,
        role=role,
        application_status=app_status,
        started=now >= request.start_at,
        in_arrive_window=request.start_at <= now < window_end,
        rated=bool(participant.rated) if participant is not None else False,
        filled=request.filled_count >= request.slots_needed,
    )
    return MatchSummary(
        id=str(request.id),
        status=_STATUS[request.status],  # type: ignore[arg-type]
        match_type=_TYPE[request.match_type],  # type: ignore[arg-type]
        slots_needed=request.slots_needed,
        filled_count=request.filled_count,
        date=request.match_date.isoformat(),
        time_slot=request.time_slot,
        start_at=format_shanghai(request.start_at),
        court=_court_out(court),
        publisher=_brief(publisher),
        expected_ntrp_min=None
        if request.expected_ntrp_min is None
        else float(request.expected_ntrp_min),
        expected_ntrp_max=None
        if request.expected_ntrp_max is None
        else float(request.expected_ntrp_max),
        gender_pref=_PREF[request.gender_pref],  # type: ignore[arg-type]
        my_role=role,  # type: ignore[arg-type]
        my_application_status=app_status,  # type: ignore[arg-type]
        my_application_id=None if application is None else str(application.id),
        available_actions=actions,
    )


async def _my_ratings(
    session: AsyncSession, request_id: int, user_id: int
) -> list[dict[str, object]]:
    rows = (
        await session.scalars(
            select(MatchRating).where(
                MatchRating.request_id == request_id,
                MatchRating.rater_id == user_id,
            )
        )
    ).all()
    return [{"rateeId": str(row.ratee_id), "score": row.score} for row in rows]


async def _participants(session: AsyncSession, request_id: int) -> list[ParticipantOut]:
    rows = (
        await session.execute(
            select(MatchParticipant, AppUser)
            .join(AppUser, AppUser.id == MatchParticipant.user_id)
            .where(MatchParticipant.request_id == request_id, MatchParticipant.status == 1)
            .order_by(MatchParticipant.role, MatchParticipant.id)
        )
    ).all()
    return [
        ParticipantOut(
            user=_brief(person),
            role="publisher" if participant.role == 1 else "partner",
            arrived=bool(participant.arrived),
            rated=bool(participant.rated),
        )
        for participant, person in rows
    ]


async def _applications_for(
    session: AsyncSession, user_id: int, request_ids: list[int]
) -> dict[int, Application]:
    if not request_ids:
        return {}
    rows = (
        await session.scalars(
            select(Application).where(
                Application.applicant_id == user_id,
                Application.request_id.in_(request_ids),
            )
        )
    ).all()
    return {int(row.request_id): row for row in rows}


async def _participant_roles(
    session: AsyncSession, user_id: int, request_ids: list[int]
) -> dict[int, MatchParticipant]:
    if not request_ids:
        return {}
    rows = (
        await session.scalars(
            select(MatchParticipant).where(
                MatchParticipant.user_id == user_id,
                MatchParticipant.request_id.in_(request_ids),
            )
        )
    ).all()
    return {int(row.request_id): row for row in rows}


async def _close_application(
    session: AsyncSession,
    application: Application,
    *,
    status: int,
    close_reason: int | None,
    action: str,
    now: datetime,
    operator_id: int,
) -> None:
    changed = await session.execute(
        update(Application)
        .where(
            Application.id == application.id,
            Application.status == 1,
            Application.version == application.version,
        )
        .values(
            status=status,
            close_reason=close_reason,
            handle_time=now,
            version=application.version + 1,
        )
    )
    if changed.rowcount != 1:
        raise ConcurrencyConflict()
    record_transition(
        session,
        entity_type="application",
        entity_id=int(application.id),
        request_id=int(application.request_id),
        action=action,
        from_status=1,
        to_status=status,
        operator_id=operator_id,
        at=now,
        detail=None if close_reason is None else {"closeReason": close_reason},
    )


async def _reject_remaining(
    session: AsyncSession,
    request: MatchRequest,
    *,
    keep_id: int,
    now: datetime,
    operator_id: int,
) -> None:
    pending = (
        await session.scalars(
            select(Application).where(
                Application.request_id == request.id,
                Application.status == 1,
                Application.id != keep_id,
            )
        )
    ).all()
    for application in pending:
        await _close_application(
            session,
            application,
            status=3,
            close_reason=2,
            action="reject",
            now=now,
            operator_id=operator_id,
        )


async def _bump(
    session: AsyncSession,
    request: MatchRequest,
    *,
    guard_capacity: bool = False,
    **values: object,
) -> None:
    conditions = [MatchRequest.id == request.id, MatchRequest.version == request.version]
    if guard_capacity:
        conditions.append(MatchRequest.status == 1)
        conditions.append(MatchRequest.filled_count < MatchRequest.slots_needed)
    changed = await session.execute(
        update(MatchRequest)
        .where(*conditions)
        .values(version=request.version + 1, **values)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise ConcurrencyConflict()


def _role(
    request: MatchRequest,
    viewer_id: int,
    application: Application | None,
    participant: MatchParticipant | None,
) -> str:
    if request.publisher_id == viewer_id:
        return "publisher"
    if participant is not None and participant.status == 1 and participant.role == 2:
        return "partner"
    if application is not None:
        return "applicant"
    return "none"


def _require_joinable(request: MatchRequest, now: datetime) -> None:
    if request.status in (2, 3) or request.filled_count >= request.slots_needed:
        raise BizError(40903, _FULL)
    if request.status != 1 or request.start_at <= now:
        raise BizError(40904, _CONFLICT)


def _require_compatible(
    viewer: AppUser,
    publisher: AppUser,
    request: MatchRequest,
    settings: Settings,
) -> None:
    if viewer.ntrp is None or publisher.ntrp is None or viewer.gender is None:
        raise BizError(40303, "不满足该约球的等级或性别要求")
    if abs(viewer.ntrp - publisher.ntrp) > settings.ntrp_hard_diff:
        raise BizError(40303, "不满足该约球的等级或性别要求")
    if request.expected_ntrp_min is not None and viewer.ntrp < request.expected_ntrp_min:
        raise BizError(40303, "不满足该约球的等级或性别要求")
    if request.expected_ntrp_max is not None and viewer.ntrp > request.expected_ntrp_max:
        raise BizError(40303, "不满足该约球的等级或性别要求")
    if request.gender_pref not in (0, viewer.gender):
        raise BizError(40303, "不满足该约球的等级或性别要求")


def _slots(match_type: str, slots_needed: int | None) -> int:
    if match_type == "singles":
        if slots_needed is None or slots_needed == 1:
            return 1
        raise BizError(
            400, "参数错误", {"errors": [{"loc": ["slotsNeeded"], "msg": "单打只能招募 1 人"}]}
        )
    if slots_needed is None:
        return 3
    if slots_needed < 1 or slots_needed > 3:
        raise BizError(
            400, "参数错误", {"errors": [{"loc": ["slotsNeeded"], "msg": "双打招募人数为 1 到 3"}]}
        )
    return slots_needed


def _narrow_expected(
    user_ntrp: Decimal,
    low: float | None,
    high: float | None,
    hard: Decimal,
) -> tuple[Decimal | None, Decimal | None]:
    if low is None and high is None:
        return None, None
    floor = user_ntrp - hard
    ceil = user_ntrp + hard
    parsed_low = floor if low is None else parse_ntrp(low)
    parsed_high = ceil if high is None else parse_ntrp(high)
    if parsed_low > parsed_high:
        raise BizError(
            400, "参数错误", {"errors": [{"loc": ["expectedNtrpMin"], "msg": "期望等级区间非法"}]}
        )
    narrowed_low = min(max(parsed_low, floor), ceil)
    narrowed_high = min(max(parsed_high, floor), ceil)
    if narrowed_low > narrowed_high:
        narrowed_low, narrowed_high = floor, ceil
    return narrowed_low, narrowed_high


def _schedule(match_date: date, time_slot: str, now: datetime) -> tuple[datetime, datetime]:
    matched = _SLOT.fullmatch(time_slot)
    if matched is None:
        raise BizError(40002, "不能选择过去的日期")
    start_clock = time.fromisoformat(matched.group(1))
    end_clock = time.fromisoformat(matched.group(2))
    start_local = datetime.combine(match_date, start_clock, tzinfo=_SHANGHAI)
    end_local = datetime.combine(match_date, end_clock, tzinfo=_SHANGHAI)
    if end_local <= start_local:
        raise BizError(40002, "不能选择过去的日期")
    start_at = start_local.astimezone(UTC).replace(tzinfo=None)
    end_at = end_local.astimezone(UTC).replace(tzinfo=None)
    today = now.replace(tzinfo=UTC).astimezone(_SHANGHAI).date()
    if match_date < today or start_at <= now:
        raise BizError(40002, "不能选择过去的日期")
    return start_at, end_at


async def _court_for_user(session: AsyncSession, raw_id: str, city: str) -> Court:
    court_id = _optional_id(raw_id, code=40003, message="球场不存在或不在当前城市")
    court = None if court_id is None else await session.get(Court, court_id)
    if court is None or court.is_deleted or not court.is_active or court.city != city:
        raise BizError(40003, "球场不存在或不在当前城市")
    return court


async def _request(session: AsyncSession, raw_id: str) -> MatchRequest:
    request_id = _optional_id(raw_id, code=404, message="资源不存在")
    request = None if request_id is None else await session.get(MatchRequest, request_id)
    if request is None or request.is_deleted:
        raise BizError(404, "资源不存在")
    return request


async def _application(session: AsyncSession, raw_id: str) -> Application:
    application_id = _optional_id(raw_id, code=404, message="资源不存在")
    application = None if application_id is None else await session.get(Application, application_id)
    if application is None:
        raise BizError(404, "资源不存在")
    return application


def _optional_id(raw: str | None, *, code: int, message: str) -> int | None:
    if raw is None:
        return None
    if not raw.isdigit() or len(raw) > 20:
        raise BizError(code, message)
    return int(raw)


def _brief(user: AppUser) -> UserBrief:
    return UserBrief(
        id=str(user.id),
        nickname=user.nickname,
        avatar=user.avatar_file_id,
        ntrp=None if user.ntrp is None else float(user.ntrp),
        gender=_GENDER.get(user.gender or 0),
        credit_score=int(user.credit_score or 0),
        avg_rating=None if user.avg_rating is None else float(user.avg_rating),
        rating_count=user.rating_count,
    )


def _court_out(court: Court):
    from tennis_match_api.schemas import CourtOut

    return CourtOut(
        id=str(court.id),
        name=court.name,
        district=court.district,
        address=court.address,
        latitude=None if court.latitude is None else float(court.latitude),
        longitude=None if court.longitude is None else float(court.longitude),
    )
