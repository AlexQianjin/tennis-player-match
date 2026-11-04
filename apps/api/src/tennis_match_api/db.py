import asyncio
import logging
from time import monotonic

import asyncmy
from asyncmy.constants import CLIENT
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from tennis_match_api.config import get_settings
from tennis_match_api.errors import DatabaseUnavailable

log = logging.getLogger(__name__)

_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None

_TRANSIENT_CODES = {2003, 2013, 1040}


def _is_transient(exc: BaseException) -> bool:
    if not isinstance(exc, asyncmy.errors.OperationalError):
        return False
    code = exc.args[0] if exc.args else None
    message = str(exc).lower()
    if code in _TRANSIENT_CODES:
        return True
    return "resuming" in message or "try connecting again" in message


async def connect_mysql(*, migration: bool = False) -> asyncmy.Connection:
    settings = get_settings()
    host, port, username, password, database = settings.mysql_endpoint(migration=migration)
    delay = 0.5
    deadline = monotonic() + settings.db_connect_max_wait_seconds
    attempt = 0
    while True:
        try:
            return await asyncmy.connect(
                host=host,
                port=port,
                user=username,
                password=password,
                db=database,
                charset="utf8mb4",
                init_command="SET time_zone = '+00:00'",
                client_flag=CLIENT.FOUND_ROWS,
                connect_timeout=5,
            )
        except asyncmy.errors.OperationalError as exc:
            attempt += 1
            if not _is_transient(exc) or monotonic() + delay > deadline:
                log.warning(
                    "db_connect_failed",
                    extra={"event": "db_connect_retry", "err": str(exc), "attempt": attempt},
                )
                raise DatabaseUnavailable() from exc
            log.warning(
                "db_connect_retry",
                extra={
                    "event": "db_connect_retry",
                    "err": str(exc),
                    "sleep": delay,
                    "attempt": attempt,
                },
            )
            await asyncio.sleep(delay)
            delay = min(delay * 2, 4)


async def connect_app() -> asyncmy.Connection:
    return await connect_mysql(migration=False)


async def connect_migrator() -> asyncmy.Connection:
    return await connect_mysql(migration=True)


def get_engine() -> AsyncEngine:
    global _engine, _sessionmaker
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            "mysql+asyncmy://",
            async_creator=connect_app,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_pre_ping=True,
            pool_recycle=settings.db_pool_recycle_seconds,
            isolation_level="READ COMMITTED",
        )
        _sessionmaker = async_sessionmaker(_engine, expire_on_commit=False)
    return _engine


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    get_engine()
    assert _sessionmaker is not None
    return _sessionmaker


async def dispose_engine() -> None:
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _sessionmaker = None
