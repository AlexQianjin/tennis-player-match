"""Cancel, leave, arrive, rate, my-matches, and the scheduler scans.

Credit changes only the counters. ``credit_score`` and ``avg_rating`` are generated.
"""

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock
from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError
from tennis_match_api.match_schemas import (
    ArriveResult,
    CancelPreview,
    CancelResult,
    MyMatchItem,
    MyMatchPage,
    RateResult,
)
from tennis_match_api.models import (
    Application,
    AppUser,
    MatchParticipant,
    MatchRating,
    MatchRequest,
)
from tennis_match_api.services.match_service import _bump, _request, _summary_for
from tennis_match_api.services.state_machine import (
    ConcurrencyConflict,
    record_transition,
    retry_on_conflict,
)

_SHANGHAI = ZoneInfo("Asia/Shanghai")
_OUTSIDE = "未到约定时间或已超过确认窗口"
_RATED = "已评分，不可修改"


def classify_tab(
    *,
    status: int,
    role: str,
    application_status: str | None,
    left: bool,
) -> str | None:
    if status == 4 or left or application_status in {"rejected", "cancelled"}:
        return "cancelled"
    if status == 3 and role in {"publisher", "partner"}:
        return "completed"
    if status == 2 and role in {"publisher", "partner"}:
        return "confirmed"
    if role == "publisher" and status == 1:
        return "pending"
    if role == "partner" and status == 1:
        return "pending"
    if application_status == "pending" and status == 1:
        return "pending"
    return None


def matches_type(
    kind: str,
    *,
    is_publisher: bool,
    has_application: bool,
    is_participant: bool,
    reached_matched: bool,
) -> bool:
    if kind == "all":
        return True
    if kind == "published":
        return is_publisher
    if kind == "applied":
        return has_application
    if kind == "matched":
        return is_participant and reached_matched
    return False


async def cancel_preview(
    session: AsyncSession,
    user: AppUser,
    request_id: str,
    clock: Clock,
) -> CancelPreview:
    request, participant = await _actor(session, user, request_id)
    counted, effect = _preview(request, participant, clock.now())
    return CancelPreview(cancel_counted=counted, effect=effect)  # type: ignore[arg-type]


@retry_on_conflict
async def cancel_match(
    session: AsyncSession,
    user: AppUser,
    request_id: str,
    reason: str | None,
    settings: Settings,
    clock: Clock,
) -> CancelResult:
    await session.refresh(user)
    request, participant = await _actor(session, user, request_id)
    now = clock.now()
    counted, effect = _preview(request, participant, now)
    detail = {"effect": effect}
    if reason:
        detail["reason"] = reason
    if participant.role == 1:
        await _publisher_cancel(session, request, user, now, detail)
    else:
        await _partner_leave(session, request, participant, user, now, detail, counted)
    await session.commit()
    summary = await _summary_for(session, user, int(request.id), settings, clock)
    return CancelResult(request=summary, cancel_counted=counted)


@retry_on_conflict
async def arrive_match(
    session: AsyncSession,
    user: AppUser,
    request_id: str,
    settings: Settings,
    clock: Clock,
) -> ArriveResult:
    await session.refresh(user)
    request = await _request(session, request_id)
    participant = await _active_participant(session, request.id, user.id)
    if participant is None or request.status not in (2, 3):
        raise BizError(403, "无权限")
    now = clock.now()
    if participant.arrived:
        summary = await _summary_for(session, user, int(request.id), settings, clock)
        return ArriveResult(arrived=True, all_arrived=request.status == 3, request=summary)
    deadline = request.start_at + timedelta(hours=settings.auto_cancel_hours)
    if request.status != 2 or not (request.start_at <= now < deadline):
        raise BizError(40302, _OUTSIDE)
    waiting = int(
        await session.scalar(
            select(func.count())
            .select_from(MatchParticipant)
            .where(
                MatchParticipant.request_id == request.id,
                MatchParticipant.status == 1,
                MatchParticipant.arrived.is_(False),
            )
        )
        or 0
    )
    changed = await session.execute(
        update(MatchParticipant)
        .where(
            MatchParticipant.id == participant.id,
            MatchParticipant.arrived.is_(False),
            MatchParticipant.version == participant.version,
        )
        .values(arrived=True, arrived_time=now, version=participant.version + 1)
    )
    if changed.rowcount != 1:
        raise ConcurrencyConflict()
    completing = waiting <= 1
    await _bump(
        session,
        request,
        status=3 if completing else 2,
        completed_time=now if completing else None,
    )
    record_transition(
        session,
        entity_type="match_request",
        entity_id=int(request.id),
        request_id=int(request.id),
        action="arrive",
        from_status=2,
        to_status=3 if completing else 2,
        at=now,
        operator_id=int(user.id),
    )
    await session.commit()
    summary = await _summary_for(session, user, int(request.id), settings, clock)
    return ArriveResult(arrived=True, all_arrived=completing, request=summary)


@retry_on_conflict
async def rate_match(
    session: AsyncSession,
    user: AppUser,
    request_id: str,
    ratings: list[tuple[str, int]],
    clock: Clock,
) -> RateResult:
    await session.refresh(user)
    request = await _request(session, request_id)
    if request.status != 3:
        raise BizError(40904, "状态已变化，请刷新后重试")
    participant = await _active_participant(session, request.id, user.id)
    if participant is None:
        raise BizError(403, "无权限")
    if participant.rated:
        raise BizError(40905, _RATED)
    others = (
        await session.scalars(
            select(MatchParticipant).where(
                MatchParticipant.request_id == request.id,
                MatchParticipant.status == 1,
                MatchParticipant.user_id != user.id,
            )
        )
    ).all()
    expected = {int(row.user_id) for row in others}
    parsed = _parse_ratings(ratings, expected, int(user.id))
    now = clock.now()
    before = int(user.credit_score or 0)
    for ratee_id, score in parsed.items():
        session.add(
            MatchRating(
                request_id=request.id,
                rater_id=user.id,
                ratee_id=ratee_id,
                score=score,
                create_time=now,
            )
        )
        await session.execute(
            update(AppUser)
            .where(AppUser.id == ratee_id)
            .values(
                rating_sum=AppUser.rating_sum + score,
                rating_count=AppUser.rating_count + 1,
            )
            .execution_options(synchronize_session=False)
        )
    changed = await session.execute(
        update(MatchParticipant)
        .where(
            MatchParticipant.id == participant.id,
            MatchParticipant.rated.is_(False),
            MatchParticipant.version == participant.version,
        )
        .values(rated=True, rated_time=now, version=participant.version + 1)
    )
    if changed.rowcount != 1:
        raise ConcurrencyConflict()
    await session.execute(
        update(AppUser)
        .where(AppUser.id == user.id)
        .values(confirm_count=AppUser.confirm_count + 1)
        .execution_options(synchronize_session=False)
    )
    await _bump(session, request)
    record_transition(
        session,
        entity_type="match_request",
        entity_id=int(request.id),
        request_id=int(request.id),
        action="rate",
        from_status=3,
        to_status=3,
        at=now,
        operator_id=int(user.id),
    )
    record_transition(
        session,
        entity_type="user_credit",
        entity_id=int(user.id),
        request_id=int(request.id),
        action="confirm_inc",
        from_status=None,
        to_status=0,
        at=now,
        operator_id=int(user.id),
        detail={"requestId": str(request.id)},
    )
    await session.flush()
    await session.refresh(user)
    after = int(user.credit_score or 0)
    await session.commit()
    return RateResult(rated=True, credit_delta=after - before, my_credit_score=after)


async def my_matches(
    session: AsyncSession,
    user: AppUser,
    *,
    kind: str,
    tab: str | None,
    page: int,
    page_size: int,
    settings: Settings,
    clock: Clock,
) -> MyMatchPage:
    published = set(
        (
            await session.scalars(
                select(MatchRequest.id).where(
                    MatchRequest.publisher_id == user.id,
                    MatchRequest.is_deleted.is_(False),
                )
            )
        ).all()
    )
    participant_rows = (
        await session.scalars(select(MatchParticipant).where(MatchParticipant.user_id == user.id))
    ).all()
    participants = {int(row.request_id): row for row in participant_rows}
    application_rows = (
        await session.scalars(select(Application).where(Application.applicant_id == user.id))
    ).all()
    applications = {int(row.request_id): row for row in application_rows}
    ids = set(published) | set(participants) | set(applications)
    if not ids:
        return MyMatchPage(items=[], page=page, page_size=page_size, total=0, has_more=False)
    requests = (
        await session.scalars(
            select(MatchRequest)
            .where(MatchRequest.id.in_(ids), MatchRequest.is_deleted.is_(False))
            .order_by(MatchRequest.start_at.desc(), MatchRequest.id.desc())
        )
    ).all()
    pending_counts = await _pending_counts(
        session,
        [int(row.id) for row in requests if row.publisher_id == user.id and row.status == 1],
    )
    items: list[MyMatchItem] = []
    for request in requests:
        application = applications.get(int(request.id))
        participant = participants.get(int(request.id))
        summary = await _summary_for(session, user, int(request.id), settings, clock)
        app_status = None if application is None else _status_name(application.status)
        left = participant is not None and participant.status == 2
        row_tab = classify_tab(
            status=request.status,
            role=summary.my_role,
            application_status=app_status,
            left=left,
        )
        if row_tab is None:
            continue
        if tab is not None and row_tab != tab:
            continue
        if not matches_type(
            kind,
            is_publisher=request.publisher_id == user.id,
            has_application=application is not None,
            is_participant=participant is not None,
            reached_matched=request.matched_time is not None or request.status == 3,
        ):
            continue
        count = pending_counts.get(int(request.id)) if request.publisher_id == user.id else None
        items.append(
            MyMatchItem(
                **summary.model_dump(),
                tab=row_tab,  # type: ignore[arg-type]
                pending_application_count=count,
            )
        )
    total = len(items)
    start = (page - 1) * page_size
    page_items = items[start : start + page_size]
    return MyMatchPage(
        items=page_items,
        page=page,
        page_size=page_size,
        total=total,
        has_more=start + len(page_items) < total,
    )


async def expire_unfilled(clock: Clock) -> int:
    return await _scan(clock, status=1, action="expire", reason=4, overdue=timedelta(0))


async def auto_cancel_unconfirmed(clock: Clock, *, hours: int = 24) -> int:
    return await _scan(
        clock,
        status=2,
        action="auto_cancel",
        reason=5,
        overdue=timedelta(hours=hours),
    )


async def _scan(clock: Clock, *, status: int, action: str, reason: int, overdue: timedelta) -> int:
    # Cutoff is the request's own start_at, not a fixed 2-hour slot boundary.
    from tennis_match_api.db import get_sessionmaker

    now = clock.now()
    cutoff = now - overdue
    factory = get_sessionmaker()
    async with factory() as session:
        ids = (
            await session.scalars(
                select(MatchRequest.id).where(
                    MatchRequest.status == status,
                    MatchRequest.start_at <= cutoff,
                    MatchRequest.is_deleted.is_(False),
                )
            )
        ).all()
    changed = 0
    for request_id in ids:
        if await _system_cancel(int(request_id), now, action, reason):
            changed += 1
    return changed


async def _system_cancel(request_id: int, now: datetime, action: str, reason: int) -> bool:
    from tennis_match_api.db import get_sessionmaker

    factory = get_sessionmaker()
    async with factory() as session:
        request = await session.get(MatchRequest, request_id)
        if request is None or request.is_deleted or request.status not in (1, 2):
            return False
        origin = request.status
        if action == "expire" and origin != 1:
            return False
        if action == "auto_cancel" and origin != 2:
            return False
        await _seal_applications(session, request, now, action, operator_id=None, operator_type=2)
        changed = await session.execute(
            update(MatchRequest)
            .where(
                MatchRequest.id == request.id,
                MatchRequest.version == request.version,
                MatchRequest.status == origin,
            )
            .execution_options(synchronize_session=False)
            .values(
                status=4,
                cancel_reason=reason,
                cancelled_time=now,
                version=request.version + 1,
            )
        )
        if changed.rowcount != 1:
            await session.rollback()
            return False
        record_transition(
            session,
            entity_type="match_request",
            entity_id=int(request.id),
            request_id=int(request.id),
            action=action,
            from_status=origin,
            to_status=4,
            at=now,
            operator_type=2,
        )
        await session.commit()
        return True


async def purge_stale_llm(clock: Clock) -> None:
    from sqlalchemy import text

    from tennis_match_api.db import get_sessionmaker

    now = clock.now()
    today = now.replace(tzinfo=UTC).astimezone(_SHANGHAI).date()
    cutoff = today - timedelta(days=30)
    factory = get_sessionmaker()
    async with factory() as session:
        await session.execute(
            text("DELETE FROM llm_match_cache WHERE expire_time < :now"),
            {"now": now},
        )
        await session.execute(
            text("DELETE FROM llm_usage_daily WHERE usage_date < :cutoff"),
            {"cutoff": cutoff},
        )
        await session.commit()


async def _publisher_cancel(
    session: AsyncSession,
    request: MatchRequest,
    user: AppUser,
    now: datetime,
    detail: dict[str, object],
) -> None:
    origin = request.status
    reason = 1 if origin == 1 else 2
    await _seal_applications(
        session, request, now, "cancel", operator_id=int(user.id), operator_type=1
    )
    await _bump(
        session,
        request,
        status=4,
        cancel_reason=reason,
        cancelled_by=user.id,
        cancelled_time=now,
    )
    if origin == 2:
        await _add_cancel(session, int(user.id), int(request.id), now)
    record_transition(
        session,
        entity_type="match_request",
        entity_id=int(request.id),
        request_id=int(request.id),
        action="cancel",
        from_status=origin,
        to_status=4,
        at=now,
        operator_id=int(user.id),
        detail=detail,
    )


async def _partner_leave(
    session: AsyncSession,
    request: MatchRequest,
    participant: MatchParticipant,
    user: AppUser,
    now: datetime,
    detail: dict[str, object],
    counted: bool,
) -> None:
    origin = request.status
    filled = request.filled_count
    changed = await session.execute(
        update(MatchParticipant)
        .where(
            MatchParticipant.id == participant.id,
            MatchParticipant.status == 1,
            MatchParticipant.version == participant.version,
        )
        .values(status=2, left_time=now, version=participant.version + 1)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise ConcurrencyConflict()
    application = await session.scalar(
        select(Application).where(
            Application.request_id == request.id,
            Application.applicant_id == user.id,
        )
    )
    if application is not None and application.status == 2:
        await _seal_one(
            session,
            application,
            now,
            action="leave",
            close_reason=5,
            operator_id=int(user.id),
            operator_type=1,
        )
    if origin == 1:
        await _bump(session, request, filled_count=filled - 1)
        target = 1
    elif now < request.start_at:
        await _bump(
            session,
            request,
            status=1,
            filled_count=filled - 1,
            matched_time=None,
        )
        target = 1
    else:
        await _seal_applications(
            session, request, now, "cancel", operator_id=int(user.id), operator_type=1
        )
        await _bump(
            session,
            request,
            status=4,
            cancel_reason=3,
            cancelled_by=user.id,
            cancelled_time=now,
        )
        target = 4
    if counted:
        await _add_cancel(session, int(user.id), int(request.id), now)
    record_transition(
        session,
        entity_type="match_request",
        entity_id=int(request.id),
        request_id=int(request.id),
        action="leave",
        from_status=origin,
        to_status=target,
        at=now,
        operator_id=int(user.id),
        detail=detail,
    )


async def _seal_applications(
    session: AsyncSession,
    request: MatchRequest,
    now: datetime,
    action: str,
    *,
    operator_id: int | None,
    operator_type: int,
) -> None:
    rows = (
        await session.scalars(
            select(Application).where(
                Application.request_id == request.id,
                Application.status.in_((1, 2)),
            )
        )
    ).all()
    for application in rows:
        await _seal_one(
            session,
            application,
            now,
            action=action,
            close_reason=4,
            operator_id=operator_id,
            operator_type=operator_type,
        )


async def _seal_one(
    session: AsyncSession,
    application: Application,
    now: datetime,
    *,
    action: str,
    close_reason: int,
    operator_id: int | None,
    operator_type: int,
) -> None:
    origin = application.status
    changed = await session.execute(
        update(Application)
        .where(
            Application.id == application.id,
            Application.status == application.status,
            Application.version == application.version,
        )
        .values(
            status=4,
            close_reason=close_reason,
            handle_time=now,
            version=application.version + 1,
        )
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise ConcurrencyConflict()
    record_transition(
        session,
        entity_type="application",
        entity_id=int(application.id),
        request_id=int(application.request_id),
        action=action,
        from_status=origin,
        to_status=4,
        at=now,
        operator_id=operator_id,
        operator_type=operator_type,
        detail={"closeReason": close_reason},
    )


async def _add_cancel(session: AsyncSession, user_id: int, request_id: int, now: datetime) -> None:
    await session.execute(
        update(AppUser)
        .where(AppUser.id == user_id)
        .values(cancel_count=AppUser.cancel_count + 1)
        .execution_options(synchronize_session=False)
    )
    record_transition(
        session,
        entity_type="user_credit",
        entity_id=user_id,
        request_id=request_id,
        action="cancel_inc",
        from_status=None,
        to_status=0,
        at=now,
        operator_id=user_id,
        detail={"requestId": str(request_id)},
    )


async def _actor(
    session: AsyncSession,
    user: AppUser,
    request_id: str,
) -> tuple[MatchRequest, MatchParticipant]:
    request = await _request(session, request_id)
    participant = await _active_participant(session, request.id, user.id)
    if participant is None or request.status not in (1, 2):
        raise BizError(403, "无权限")
    if participant.role == 2 and request.status == 1 and participant.status != 1:
        raise BizError(403, "无权限")
    return request, participant


def _preview(
    request: MatchRequest,
    participant: MatchParticipant,
    now: datetime,
) -> tuple[bool, str]:
    if participant.role == 1 and request.status == 1:
        return False, "cancel_all"
    if participant.role == 1 and request.status == 2:
        return True, "cancel_all"
    if participant.role == 2 and request.status == 1:
        return False, "leave"
    if participant.role == 2 and request.status == 2 and now < request.start_at:
        return True, "reopen"
    if participant.role == 2 and request.status == 2:
        return True, "cancel_all"
    raise BizError(403, "无权限")


async def _active_participant(
    session: AsyncSession,
    request_id: int,
    user_id: int,
) -> MatchParticipant | None:
    return await session.scalar(
        select(MatchParticipant).where(
            MatchParticipant.request_id == request_id,
            MatchParticipant.user_id == user_id,
            MatchParticipant.status == 1,
        )
    )


def _parse_ratings(
    ratings: list[tuple[str, int]],
    expected: set[int],
    rater_id: int,
) -> dict[int, int]:
    parsed: dict[int, int] = {}
    for raw_id, score in ratings:
        if not raw_id.isdigit():
            raise BizError(400, "参数错误")
        ratee_id = int(raw_id)
        if ratee_id == rater_id or ratee_id not in expected or ratee_id in parsed:
            raise BizError(400, "参数错误")
        parsed[ratee_id] = score
    if set(parsed) != expected:
        raise BizError(400, "参数错误")
    return parsed


def _status_name(status: int) -> str:
    return {1: "pending", 2: "agreed", 3: "rejected", 4: "cancelled"}[status]


async def _pending_counts(session: AsyncSession, request_ids: list[int]) -> dict[int, int]:
    if not request_ids:
        return {}
    rows = (
        await session.execute(
            select(Application.request_id, func.count())
            .where(Application.request_id.in_(request_ids), Application.status == 1)
            .group_by(Application.request_id)
        )
    ).all()
    return {int(request_id): int(count) for request_id, count in rows}
