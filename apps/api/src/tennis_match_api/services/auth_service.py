from time import monotonic

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock
from tennis_match_api.errors import BizError
from tennis_match_api.identity import WxIdentity
from tennis_match_api.models import AppUser
from tennis_match_api.schemas import LoginResult
from tennis_match_api.services.profile_service import build_profile


class IdentityCache:
    """openid → user id, so repeat requests skip the openid lookup."""

    def __init__(self, *, ttl_seconds: float = 60, max_size: int = 10_000) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._items: dict[str, tuple[int, float]] = {}

    def get(self, openid: str) -> int | None:
        item = self._items.get(openid)
        if item is None:
            return None
        user_id, expires_at = item
        if expires_at <= monotonic():
            self._items.pop(openid, None)
            return None
        return user_id

    def put(self, openid: str, user_id: int) -> None:
        if openid not in self._items and len(self._items) >= self._max_size:
            self._items.pop(next(iter(self._items)))
        self._items[openid] = (user_id, monotonic() + self._ttl)

    def invalidate(self, openid: str) -> None:
        self._items.pop(openid, None)


identity_cache = IdentityCache()


async def get_or_create_user(
    session: AsyncSession,
    identity: WxIdentity,
    clock: Clock,
    *,
    touch_login: bool,
) -> AppUser:
    user = await _load_cached(session, identity.openid)
    created = False
    if user is None:
        user = await session.scalar(select(AppUser).where(AppUser.openid == identity.openid))
    if user is None:
        user = AppUser(
            openid=identity.openid,
            unionid=identity.unionid,
            last_login_time=clock.now() if touch_login else None,
        )
        session.add(user)
        try:
            await session.commit()
            created = True
        except IntegrityError:
            await session.rollback()
            user = await session.scalar(select(AppUser).where(AppUser.openid == identity.openid))
            if user is None:
                raise
    if user.is_deleted:
        identity_cache.invalidate(identity.openid)
        raise BizError(403, "账号已停用")
    identity_cache.put(identity.openid, int(user.id))
    if touch_login and not created:
        user.last_login_time = clock.now()
        if identity.unionid:
            user.unionid = identity.unionid
        await session.commit()
    await session.refresh(user)
    return user


async def login_user(session: AsyncSession, identity: WxIdentity, clock: Clock) -> LoginResult:
    user = await get_or_create_user(session, identity, clock, touch_login=True)
    profile = await build_profile(session, user)
    return LoginResult(is_new_user=not bool(user.profile_completed), user_info=profile)


async def _load_cached(session: AsyncSession, openid: str) -> AppUser | None:
    user_id = identity_cache.get(openid)
    if user_id is None:
        return None
    user = await session.get(AppUser, user_id)
    if user is None or user.openid != openid:
        identity_cache.invalidate(openid)
        return None
    return user
