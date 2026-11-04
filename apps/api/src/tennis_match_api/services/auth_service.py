from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock
from tennis_match_api.errors import BizError
from tennis_match_api.identity import WxIdentity
from tennis_match_api.models import AppUser
from tennis_match_api.schemas import LoginResult, Profile

_STYLE_BITS = ((1, "singles"), (2, "doubles"), (4, "casual"), (8, "competitive"))
_REQUIRED = (
    ("nickname", "nickname"),
    ("avatar_file_id", "avatar"),
    ("ntrp", "ntrp"),
    ("gender", "gender"),
    ("age", "age"),
    ("city", "city"),
)


def to_profile(user: AppUser) -> Profile:
    gender = {1: "male", 2: "female"}.get(user.gender or 0)
    styles = [name for bit, name in _STYLE_BITS if user.style_mask & bit]
    missing = [label for attr, label in _REQUIRED if getattr(user, attr) in (None, "")]
    return Profile(
        id=str(user.id),
        nickname=user.nickname,
        avatar=user.avatar_file_id,
        ntrp=float(user.ntrp) if user.ntrp is not None else None,
        gender=gender,
        age=user.age,
        city=user.city,
        style=styles,
        bio=user.bio,
        credit_score=int(user.credit_score or 0),
        confirm_count=user.confirm_count,
        cancel_count=user.cancel_count,
        avg_rating=float(user.avg_rating) if user.avg_rating is not None else None,
        rating_count=user.rating_count,
        profile_completed=bool(user.profile_completed),
        missing_fields=missing,
    )


async def login_user(session: AsyncSession, identity: WxIdentity, clock: Clock) -> LoginResult:
    now = clock.now()
    user = await session.scalar(select(AppUser).where(AppUser.openid == identity.openid))
    created = False
    if user is None:
        user = AppUser(openid=identity.openid, unionid=identity.unionid, last_login_time=now)
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
        raise BizError(403, "账号已停用")
    if not created:
        user.last_login_time = now
        if identity.unionid:
            user.unionid = identity.unionid
        await session.commit()
    await session.refresh(user)
    return LoginResult(is_new_user=not user.profile_completed, user_info=to_profile(user))
