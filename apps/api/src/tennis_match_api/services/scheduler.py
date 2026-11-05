"""In-process scans. Business changes go through the same Python transitions as users."""

from collections.abc import Awaitable, Callable

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import text

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.config import Settings, get_settings
from tennis_match_api.db import get_engine
from tennis_match_api.services.lifecycle_service import (
    auto_cancel_unconfirmed,
    expire_unfilled,
    purge_stale_llm,
)

_scheduler: AsyncIOScheduler | None = None


async def run_exclusive(name: str, job: Callable[[], Awaitable[None]]) -> bool:
    engine = get_engine()
    async with engine.connect() as conn:
        got = (await conn.execute(text("SELECT GET_LOCK(:name, 0)"), {"name": name})).scalar()
        held = int(got or 0) == 1
        try:
            if not held:
                return False
            await job()
            return True
        finally:
            if held:
                await conn.execute(text("SELECT RELEASE_LOCK(:name)"), {"name": name})
            await conn.commit()


async def run_due_scans(clock: Clock | None = None) -> None:
    settings = get_settings()
    current = clock or get_clock()
    await expire_unfilled(current)
    await auto_cancel_unconfirmed(current, hours=settings.auto_cancel_hours)


async def startup_catchup(clock: Clock | None = None) -> bool:
    current = clock or get_clock()
    return await run_exclusive("tennis:scheduler", lambda: run_due_scans(current))


def start_scheduler(settings: Settings) -> None:
    global _scheduler
    if _scheduler is not None:
        return
    scheduler = AsyncIOScheduler(timezone=settings.business_tz)
    scheduler.add_job(
        _interval_scan,
        "interval",
        seconds=settings.scheduler_interval_seconds,
        id="tennis-scans",
        replace_existing=True,
    )
    scheduler.add_job(
        _purge,
        "cron",
        hour=4,
        minute=0,
        id="tennis-purge-llm",
        replace_existing=True,
    )
    scheduler.start()
    _scheduler = scheduler


async def stop_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None


async def _interval_scan() -> None:
    await run_exclusive("tennis:scheduler", run_due_scans)


async def _purge() -> None:
    await run_exclusive("tennis:scheduler", lambda: purge_stale_llm(get_clock()))
