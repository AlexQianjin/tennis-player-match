"""Cache, daily quota, timeout, and recommend rerank inputs."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import bindparam, text
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock
from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError
from tennis_match_api.models import AppUser, MatchRequest
from tennis_match_api.services.llm.client import LLMClient
from tennis_match_api.services.llm.parser import parse_scores
from tennis_match_api.services.llm.prompt import (
    PROMPT_VERSION,
    SYSTEM_PROMPT,
    input_hash,
    recommend_prompt,
)
from tennis_match_api.services.ranking import final_score

log = logging.getLogger(__name__)
_SHANGHAI = ZoneInfo("Asia/Shanghai")
_background: set[asyncio.Task[None]] = set()


@dataclass(frozen=True)
class LlmMark:
    score: int | None
    final: float | None
    reason: str | None


class _OverLimit(Exception):
    pass


def spawn(coro) -> None:
    task = asyncio.create_task(coro)
    _background.add(task)
    task.add_done_callback(_background.discard)


async def cancel_background() -> None:
    tasks = list(_background)
    for task in tasks:
        task.cancel()
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)


async def annotate_recommend(
    session: AsyncSession,
    viewer: AppUser,
    rows: list[tuple[float, float, datetime, int, MatchRequest, AppUser]],
    *,
    settings: Settings,
    clock: Clock,
    client: LLMClient | None,
    page: int,
    use_cache: bool = True,
) -> tuple[dict[int, LlmMark], bool]:
    """Score the rule shortlist. Returns marks keyed by request id and llmApplied."""
    if not rows or viewer.ntrp is None:
        return {}, False
    shortlist = rows[: settings.llm_top_n]
    now = clock.now()
    metas = []
    for credit, closeness, _start, request_id, request, publisher in shortlist:
        digest = input_hash(
            publisher,
            viewer,
            request,
            prompt_version=settings.llm_prompt_version or PROMPT_VERSION,
            model_name=settings.ai_model_name or "",
        )
        metas.append((request_id, publisher, request, credit, closeness, digest))
    cached = (
        await _read_cache(session, viewer.id, [item[0] for item in metas], now) if use_cache else {}
    )
    hits = {
        request_id: cached[(publisher.id, viewer.id)]
        for request_id, publisher, _request, _credit, _closeness, digest in metas
        if (publisher.id, viewer.id) in cached and cached[(publisher.id, viewer.id)][0] == digest
    }
    reasons = {request_id: row[2] for request_id, row in hits.items()}
    allow_call = page < 3 and client is not None and settings.llm_enabled
    missing = [item for item in metas if item[0] not in hits]
    if not missing and hits:
        _log("ok", 0, len(hits), asyncio.get_running_loop().time(), settings)
        scores = {item[0]: hits[item[0]][1] for item in metas}
        return _applied(metas, scores, reasons, settings), True
    if not allow_call or not missing:
        return _reasons_only(reasons), False
    if not await _consume(session, int(viewer.id), clock, settings):
        log.info(
            "llm_call",
            extra={
                "event": "llm_call",
                "candidates": len(missing),
                "cache_hits": len(hits),
                "outcome": "limit",
                "model": settings.ai_model_name,
                "prompt_version": settings.llm_prompt_version,
            },
        )
        return _reasons_only(reasons), False
    # Persist the quota before waiting so a timeout still counts for the day.
    await session.commit()
    return await _call_model(
        session, viewer, metas, hits, reasons, missing, settings, clock, client
    )


async def _call_model(
    session: AsyncSession,
    viewer: AppUser,
    metas: list[tuple[int, AppUser, MatchRequest, float, float, str]],
    hits: dict[int, tuple[str, int, str | None]],
    reasons: dict[int, str | None],
    missing: list[tuple[int, AppUser, MatchRequest, float, float, str]],
    settings: Settings,
    clock: Clock,
    client: LLMClient,
) -> tuple[dict[int, LlmMark], bool]:
    short_ids = {f"r{index + 1}": item[0] for index, item in enumerate(missing)}
    prompt_rows = [
        (short, item[1], item[2]) for short, item in zip(short_ids, missing, strict=True)
    ]
    prompt = recommend_prompt(viewer, prompt_rows)
    started = asyncio.get_running_loop().time()
    task = asyncio.create_task(client.complete(system=SYSTEM_PROMPT, user=prompt))
    try:
        raw = await asyncio.wait_for(asyncio.shield(task), timeout=settings.llm_timeout_seconds)
    except TimeoutError:
        spawn(_finish_in_background(task, missing, int(viewer.id), settings, clock))
        _log("timeout", len(missing), len(hits), started, settings)
        return _reasons_only(reasons), False
    except Exception:
        _log("error", len(missing), len(hits), started, settings)
        return _reasons_only(reasons), False
    parsed, outcome = parse_scores(raw, list(short_ids))
    if outcome != "ok":
        log.warning(
            "llm_call",
            extra={
                "event": "llm_call",
                "outcome": "bad_output",
                "snippet": raw[:500],
                "candidates": len(missing),
                "cache_hits": len(hits),
                "model": settings.ai_model_name,
                "prompt_version": settings.llm_prompt_version,
            },
        )
        return _reasons_only(reasons), False
    fresh: dict[int, int] = {}
    store: list[tuple[int, int, str | None, str]] = []
    for short, request_id in short_ids.items():
        item = parsed[short]
        fresh[request_id] = item.score
        if item.store:
            digest = next(row[5] for row in missing if row[0] == request_id)
            store.append((request_id, item.score, item.reason, digest))
            reasons[request_id] = item.reason
        elif request_id in reasons:
            pass
    if store:
        await _write_cache(session, viewer.id, store, missing, settings, clock.now())
        await session.commit()
    scores = {request_id: hits[request_id][1] for request_id in hits}
    scores.update(fresh)
    _log("ok", len(missing), len(hits), started, settings)
    return _applied(metas, scores, reasons, settings), True


def _applied(
    metas: list[tuple[int, AppUser, MatchRequest, float, float, str]],
    scores: dict[int, int],
    reasons: dict[int, str | None],
    settings: Settings,
) -> dict[int, LlmMark]:
    marks: dict[int, LlmMark] = {}
    for request_id, _publisher, _request, credit, closeness, _digest in metas:
        score = scores.get(request_id)
        final = final_score(
            credit,
            closeness,
            score,
            weight_credit=settings.rank_weight_credit,
            weight_ntrp=settings.rank_weight_ntrp,
            weight_llm=settings.rank_weight_llm,
        )
        marks[request_id] = LlmMark(score=score, final=final, reason=reasons.get(request_id))
    return marks


def _reasons_only(reasons: dict[int, str | None]) -> dict[int, LlmMark]:
    return {
        request_id: LlmMark(score=None, final=None, reason=reason)
        for request_id, reason in reasons.items()
        if reason
    }


async def _finish_in_background(
    task: asyncio.Task[str],
    missing: list[tuple[int, AppUser, MatchRequest, float, float, str]],
    candidate_id: int,
    settings: Settings,
    clock: Clock,
) -> None:
    try:
        raw = await asyncio.wait_for(task, timeout=settings.llm_background_timeout_seconds)
        parsed, outcome = parse_scores(raw, [f"r{index + 1}" for index in range(len(missing))])
        if outcome != "ok":
            return
        store: list[tuple[int, int, str | None, str]] = []
        for index, item in enumerate(missing):
            parsed_item = parsed.get(f"r{index + 1}")
            if parsed_item is None or not parsed_item.store:
                continue
            store.append((item[0], parsed_item.score, parsed_item.reason, item[5]))
        if not store:
            return
        from tennis_match_api.db import get_sessionmaker

        factory = get_sessionmaker()
        async with factory() as session:
            await _write_cache(session, candidate_id, store, missing, settings, clock.now())
            await session.commit()
    except Exception:
        log.info("llm_call", extra={"event": "llm_call", "outcome": "timeout", "background": True})


def _log(outcome: str, candidates: int, hits: int, started: float, settings: Settings) -> None:
    log.info(
        "llm_call",
        extra={
            "event": "llm_call",
            "candidates": candidates,
            "cache_hits": hits,
            "latency_ms": round((asyncio.get_running_loop().time() - started) * 1000, 2),
            "outcome": outcome,
            "model": settings.ai_model_name,
            "prompt_version": settings.llm_prompt_version,
        },
    )


async def _consume(session: AsyncSession, user_id: int, clock: Clock, settings: Settings) -> bool:
    usage_date = clock.now().replace(tzinfo=UTC).astimezone(_SHANGHAI).date()
    try:
        async with session.begin_nested():
            for scope, limit in (
                ("global", settings.llm_daily_limit_global),
                (f"user:{user_id}", settings.llm_daily_limit_per_user),
            ):
                await session.execute(
                    text("INSERT IGNORE INTO llm_usage_daily (usage_date, scope) VALUES (:d, :s)"),
                    {"d": usage_date, "s": scope},
                )
                changed = await session.execute(
                    text(
                        "UPDATE llm_usage_daily SET call_count = call_count + 1 "
                        "WHERE usage_date = :d AND scope = :s AND call_count < :limit"
                    ),
                    {"d": usage_date, "s": scope, "limit": limit},
                )
                if changed.rowcount != 1:
                    raise _OverLimit()
    except _OverLimit:
        return False
    return True


async def _read_cache(
    session: AsyncSession,
    candidate_id: int,
    request_ids: list[int],
    now: datetime,
) -> dict[tuple[int, int], tuple[str, int, str | None]]:
    del request_ids
    rows = (
        await session.execute(
            text(
                "SELECT publisher_id, candidate_id, input_hash, llm_score, reason, expire_time "
                "FROM llm_match_cache WHERE candidate_id = :cid AND expire_time > :now"
            ),
            {"cid": candidate_id, "now": now},
        )
    ).all()
    return {
        (int(publisher_id), int(candidate_id_)): (str(digest), int(score), reason)
        for publisher_id, candidate_id_, digest, score, reason, _expire in rows
    }


async def _write_cache(
    session: AsyncSession,
    candidate_id: int,
    store: list[tuple[int, int, str | None, str]],
    missing: list[tuple[int, AppUser, MatchRequest, float, float, str]],
    settings: Settings,
    now: datetime,
) -> None:
    publishers = {request_id: publisher.id for request_id, publisher, *_rest in missing}
    expire = now + timedelta(days=settings.llm_cache_ttl_days)
    model = settings.ai_model_name or ""
    version = settings.llm_prompt_version or PROMPT_VERSION
    for request_id, score, reason, digest in store:
        publisher_id = publishers[request_id]
        existing = (
            await session.execute(
                text(
                    "SELECT id FROM llm_match_cache "
                    "WHERE publisher_id = :pid AND candidate_id = :cid"
                ),
                {"pid": publisher_id, "cid": candidate_id},
            )
        ).first()
        params = {
            "pid": publisher_id,
            "cid": candidate_id,
            "digest": digest,
            "score": score,
            "reason": reason,
            "model": model,
            "version": version,
            "expire": expire,
        }
        if existing is None:
            await session.execute(
                text(
                    "INSERT INTO llm_match_cache "
                    "(publisher_id, candidate_id, input_hash, llm_score, reason, "
                    "model_name, prompt_version, expire_time) "
                    "VALUES (:pid, :cid, :digest, :score, :reason, :model, :version, :expire)"
                ),
                params,
            )
        else:
            await session.execute(
                text(
                    "UPDATE llm_match_cache SET input_hash = :digest, llm_score = :score, "
                    "reason = :reason, model_name = :model, prompt_version = :version, "
                    "expire_time = :expire WHERE publisher_id = :pid AND candidate_id = :cid"
                ),
                params,
            )


async def debug_score(
    session: AsyncSession,
    settings: Settings,
    clock: Clock,
    client: LLMClient | None,
    *,
    publisher_id: str,
    candidate_ids: list[str],
    request_id: str | None,
    use_cache: bool,
) -> dict[str, object]:
    from tennis_match_api.models import MatchRequest
    from tennis_match_api.services.ranking import credit_norm, ntrp_closeness

    if not publisher_id.isdigit():
        raise BizError(400, "参数错误")
    publisher = await session.get(AppUser, int(publisher_id))
    if publisher is None or publisher.ntrp is None:
        raise BizError(404, "资源不存在")
    if request_id is None:
        request = MatchRequest(
            id=0,
            publisher_id=publisher.id,
            match_type=1,
            gender_pref=0,
            start_at=clock.now(),
        )
    elif request_id.isdigit():
        loaded = await session.get(MatchRequest, int(request_id))
        if loaded is None:
            raise BizError(404, "资源不存在")
        request = loaded
    else:
        raise BizError(400, "参数错误")
    results: list[dict[str, object]] = []
    for raw_id in candidate_ids:
        if not raw_id.isdigit():
            raise BizError(400, "参数错误")
        candidate = await session.get(AppUser, int(raw_id))
        if candidate is None or candidate.ntrp is None:
            raise BizError(404, "资源不存在")
        credit = credit_norm(int(publisher.credit_score or 0), settings.credit_norm_cap)
        closeness = ntrp_closeness(publisher.ntrp, candidate.ntrp, settings.ntrp_hard_diff)
        marks, applied = await annotate_recommend(
            session,
            candidate,
            [(credit, closeness, request.start_at, int(request.id), request, publisher)],
            settings=settings,
            clock=clock,
            client=client,
            page=1,
            use_cache=use_cache,
        )
        mark = marks.get(int(request.id))
        results.append(
            {
                "candidateId": raw_id,
                "score": None if mark is None else mark.score,
                "reason": None if mark is None else mark.reason,
                "source": "llm" if applied else "cache" if mark and mark.reason else "default",
                "latencyMs": 0,
            }
        )
    outcome = "ok" if any(row["source"] == "llm" for row in results) else "disabled"
    return {"results": results, "outcome": outcome}


async def cached_application_notes(
    session: AsyncSession,
    publisher: AppUser,
    request: MatchRequest,
    applicants: list[AppUser],
    *,
    settings: Settings,
    now: datetime,
) -> dict[int, tuple[int, str | None]]:
    if not applicants:
        return {}
    ids = [int(user.id) for user in applicants]
    statement = text(
        "SELECT candidate_id, input_hash, llm_score, reason, expire_time "
        "FROM llm_match_cache WHERE publisher_id = :pid AND candidate_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True))
    rows = (await session.execute(statement, {"pid": int(publisher.id), "ids": ids})).all()
    notes: dict[int, tuple[int, str | None]] = {}
    for candidate_id, digest, score, reason, expire in rows:
        if expire <= now:
            continue
        user = next(item for item in applicants if int(item.id) == int(candidate_id))
        expected = input_hash(
            publisher,
            user,
            request,
            prompt_version=settings.llm_prompt_version or PROMPT_VERSION,
            model_name=settings.ai_model_name or "",
        )
        if digest == expected:
            notes[int(candidate_id)] = (int(score), reason)
    return notes
