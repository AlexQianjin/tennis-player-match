from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.config import Settings, get_settings
from tennis_match_api.db import get_sessionmaker
from tennis_match_api.identity import WxIdentity, resolve_identity
from tennis_match_api.models import AppUser
from tennis_match_api.services.auth_service import get_or_create_user


async def get_session() -> AsyncIterator[AsyncSession]:
    factory = get_sessionmaker()
    async with factory() as session:
        yield session


def get_identity(
    request: Request,
    settings: Annotated[Settings, Depends(get_settings)],
) -> WxIdentity:
    return resolve_identity(request.headers, settings)


async def get_current_user(
    identity: Annotated[WxIdentity, Depends(get_identity)],
    session: Annotated[AsyncSession, Depends(get_session)],
    clock: Annotated[Clock, Depends(get_clock)],
) -> AppUser:
    return await get_or_create_user(session, identity, clock, touch_login=False)


__all__ = [
    "Clock",
    "get_clock",
    "get_current_user",
    "get_identity",
    "get_session",
    "get_settings",
]
