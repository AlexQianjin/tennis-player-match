"""Allowed match transitions and the audit log.

Arrive, rate, expire, and credit changes are described here so later milestones
call the same table. M2 only commits publish, apply, withdraw, agree, and reject.
"""

import logging
from collections.abc import Awaitable, Callable
from datetime import datetime
from functools import wraps

from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.errors import BizError
from tennis_match_api.models.match import StateTransitionLog

log = logging.getLogger(__name__)

# (entity_type, from_status, action) -> allowed to_status values. from_status None is create.
ALLOWED: dict[tuple[str, int | None, str], frozenset[int]] = {
    ("match_request", None, "publish"): frozenset({1}),
    ("match_request", 1, "agree"): frozenset({1, 2}),
    ("match_request", 1, "reject"): frozenset({1}),
    ("match_request", 1, "cancel"): frozenset({4}),
    ("match_request", 1, "leave"): frozenset({1}),
    ("match_request", 1, "expire"): frozenset({4}),
    ("match_request", 2, "cancel"): frozenset({4}),
    ("match_request", 2, "leave"): frozenset({1, 4}),
    ("match_request", 2, "arrive"): frozenset({2, 3}),
    ("match_request", 2, "auto_cancel"): frozenset({4}),
    ("match_request", 3, "rate"): frozenset({3}),
    ("application", None, "apply"): frozenset({1}),
    ("application", 1, "agree"): frozenset({2}),
    ("application", 1, "reject"): frozenset({3}),
    ("application", 1, "withdraw"): frozenset({4}),
    ("application", 1, "cancel"): frozenset({4}),
    ("application", 1, "expire"): frozenset({4}),
    ("application", 2, "cancel"): frozenset({4}),
    ("application", 2, "expire"): frozenset({4}),
    ("application", 2, "leave"): frozenset({4}),
}


class TransitionError(Exception):
    def __init__(self, entity: str, from_status: int | None, action: str, to_status: int) -> None:
        super().__init__(f"{entity} {from_status} -{action}-> {to_status}")
        self.entity = entity
        self.from_status = from_status
        self.action = action
        self.to_status = to_status


class ConcurrencyConflict(Exception):
    """Optimistic lock missed. The caller retries the whole use case."""


def ensure_transition(entity: str, from_status: int | None, action: str, to_status: int) -> None:
    allowed = ALLOWED.get((entity, from_status, action))
    if allowed is None or to_status not in allowed:
        raise TransitionError(entity, from_status, action, to_status)


def record_transition(
    session: AsyncSession,
    *,
    entity_type: str,
    entity_id: int,
    request_id: int | None,
    action: str,
    from_status: int | None,
    to_status: int,
    operator_id: int,
    at: datetime,
    detail: dict[str, object] | None = None,
) -> None:
    ensure_transition(entity_type, from_status, action, to_status)
    row = StateTransitionLog(
        entity_type=entity_type,
        entity_id=entity_id,
        request_id=request_id,
        action=action,
        from_status=from_status,
        to_status=to_status,
        operator_type=1,
        operator_id=operator_id,
        create_time=at,
    )
    # JSON null is not a JSON object; leave the column unset so MySQL stores SQL NULL.
    if detail is not None:
        row.detail = detail
    session.add(row)
    log.info(
        "state_transition",
        extra={
            "event": "state_transition",
            "entity": entity_type,
            "id": entity_id,
            "from": from_status,
            "to": to_status,
            "action": action,
            "operator": f"user:{operator_id}",
        },
    )


def retry_on_conflict[**P, R](fn: Callable[P, Awaitable[R]]) -> Callable[P, Awaitable[R]]:
    @wraps(fn)
    async def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
        session = _find_session(args, kwargs)
        last: ConcurrencyConflict | None = None
        for _ in range(3):
            try:
                return await fn(*args, **kwargs)
            except ConcurrencyConflict as exc:
                last = exc
                if session is not None:
                    await session.rollback()
        raise BizError(40904, "状态已变化，请刷新后重试") from last

    return wrapper


def _find_session(args: tuple[object, ...], kwargs: dict[str, object]) -> AsyncSession | None:
    candidate = kwargs.get("session")
    if isinstance(candidate, AsyncSession):
        return candidate
    for arg in args:
        if isinstance(arg, AsyncSession):
            return arg
    return None


def available_actions(
    *,
    status: int,
    role: str,
    application_status: str | None,
    started: bool,
    in_arrive_window: bool,
    rated: bool,
    filled: bool,
) -> list[str]:
    """Actions the current user may take. Arrive/rate/cancel are listed for M3."""
    if role == "publisher" and status == 1:
        return ["viewApplications", "cancel"]
    if role == "applicant" and application_status == "pending" and status == 1:
        return ["withdraw"]
    if role == "none" and status == 1 and not started and not filled:
        return ["apply"]
    if role == "partner" and status == 1:
        return ["cancel"]
    if role in {"publisher", "partner"} and status == 2:
        actions = ["cancel"]
        if in_arrive_window:
            actions.append("arrive")
        return actions
    if role in {"publisher", "partner"} and status == 3 and not rated:
        return ["rate"]
    return []
