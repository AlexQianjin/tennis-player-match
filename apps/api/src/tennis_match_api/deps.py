from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.config import Settings, get_settings
from tennis_match_api.db import get_sessionmaker
from tennis_match_api.identity import WxIdentity, resolve_identity


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_sessionmaker()
    async with factory() as session:
        yield session


def get_identity(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> WxIdentity:
    return resolve_identity(request.headers, settings)


__all__ = ["Clock", "get_clock", "get_identity", "get_session", "get_settings"]
