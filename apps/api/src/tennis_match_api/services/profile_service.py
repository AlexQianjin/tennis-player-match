"""Profile reads and partial updates.

Publish, recommend, and apply (M2) must call ``ensure_profile_completed``
before they run. Those routes are intentionally not registered in M1.
"""

from datetime import datetime

from sqlalchemy import text, update
from sqlalchemy.ext.asyncio import AsyncSession

from tennis_match_api.clock import Clock
from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError
from tennis_match_api.models import AppUser
from tennis_match_api.ntrp import parse_ntrp, same_ntrp
from tennis_match_api.schemas import Profile, ProfileUpdate, UserPublic
from tennis_match_api.services.avatar import validate_avatar_file_id
from tennis_match_api.timefmt import add_months, format_shanghai

_STYLE_ORDER = (
    ("singles", 1),
    ("doubles", 2),
    ("casual", 4),
    ("competitive", 8),
)
_GENDER_TO_CODE = {"male": 1, "female": 2}
_CODE_TO_GENDER = {1: "male", 2: "female"}
_REQUIRED = (
    ("nickname", "nickname"),
    ("avatar_file_id", "avatar"),
    ("ntrp", "ntrp"),
    ("gender", "gender"),
    ("age", "age"),
    ("city", "city"),
)


def ensure_profile_completed(user: AppUser) -> None:
    if not user.profile_completed:
        raise BizError(40001, "资料未完善，请先完善资料")


def mask_to_styles(mask: int) -> list[str]:
    return [name for name, bit in _STYLE_ORDER if mask & bit]


def style_to_mask(styles: list[str]) -> int:
    bits = dict(_STYLE_ORDER)
    mask = 0
    for name in styles:
        mask |= bits[name]
    return mask


def profile_from_user(user: AppUser, *, active_request_id: str | None = None) -> Profile:
    missing = [label for attr, label in _REQUIRED if getattr(user, attr) in (None, "")]
    ntrp_update = user.ntrp_update_time
    next_editable = None if ntrp_update is None else format_shanghai(add_months(ntrp_update, 1))
    return Profile(
        id=str(user.id),
        nickname=user.nickname,
        avatar=user.avatar_file_id,
        ntrp=float(user.ntrp) if user.ntrp is not None else None,
        gender=_CODE_TO_GENDER.get(user.gender or 0),
        age=user.age,
        city=user.city,
        style=mask_to_styles(user.style_mask or 0),
        bio=user.bio,
        credit_score=int(user.credit_score or 0),
        confirm_count=user.confirm_count,
        cancel_count=user.cancel_count,
        avg_rating=float(user.avg_rating) if user.avg_rating is not None else None,
        rating_count=user.rating_count,
        profile_completed=bool(user.profile_completed),
        missing_fields=missing,
        ntrp_update_time=None if ntrp_update is None else format_shanghai(ntrp_update),
        ntrp_next_editable_at=next_editable,
        active_request_id=active_request_id,
    )


def public_from_user(user: AppUser) -> UserPublic:
    return UserPublic(
        id=str(user.id),
        nickname=user.nickname,
        avatar=user.avatar_file_id,
        ntrp=float(user.ntrp) if user.ntrp is not None else None,
        gender=_CODE_TO_GENDER.get(user.gender or 0),
        credit_score=int(user.credit_score or 0),
        avg_rating=float(user.avg_rating) if user.avg_rating is not None else None,
        rating_count=user.rating_count,
        age=user.age,
        city=user.city,
        style=mask_to_styles(user.style_mask or 0),
        bio=user.bio,
    )


async def build_profile(session: AsyncSession, user: AppUser) -> Profile:
    active_request_id = await _active_request_id(session, int(user.id))
    return profile_from_user(user, active_request_id=active_request_id)


async def get_public_profile(session: AsyncSession, user_id: int) -> UserPublic:
    user = await session.get(AppUser, user_id)
    if user is None or user.is_deleted:
        raise BizError(404, "资源不存在")
    return public_from_user(user)


def parse_public_user_id(raw: str) -> int:
    if not raw.isdigit() or len(raw) > 20:
        raise BizError(404, "资源不存在")
    return int(raw)


async def update_profile(
    session: AsyncSession,
    user: AppUser,
    payload: ProfileUpdate,
    settings: Settings,
    clock: Clock,
) -> Profile:
    changes = payload.model_dump(exclude_unset=True)
    nickname = user.nickname
    avatar = user.avatar_file_id
    gender = user.gender
    age = user.age
    city = user.city
    style_mask = user.style_mask or 0
    bio = user.bio
    ntrp = user.ntrp
    ntrp_update_time = user.ntrp_update_time

    if "nickname" in changes:
        nickname = _present("nickname", changes["nickname"])
    if "avatar" in changes:
        avatar = _present("avatar", changes["avatar"])
        validate_avatar_file_id(avatar, settings)
    if "gender" in changes:
        gender_name = _present("gender", changes["gender"])
        gender = _GENDER_TO_CODE[gender_name]
    if "age" in changes:
        age = _present("age", changes["age"])
    if "city" in changes:
        city = _present("city", changes["city"])
        if city not in settings.supported_cities:
            raise BizError(
                400,
                "城市不在支持列表",
                {"errors": [{"loc": ["city"], "msg": "城市不在支持列表"}]},
            )
    if "style" in changes:
        styles = changes["style"] if changes["style"] is not None else []
        style_mask = style_to_mask(styles)
    if "bio" in changes:
        bio = changes["bio"] or None
    if "ntrp" in changes:
        incoming = parse_ntrp(_present("ntrp", changes["ntrp"]))
        if not same_ntrp(user.ntrp, incoming):
            if user.ntrp is not None:
                ntrp_update_time = _claim_ntrp_change(user.ntrp_update_time, clock)
            ntrp = incoming

    completed = all(
        (
            nickname not in (None, ""),
            avatar not in (None, ""),
            ntrp is not None,
            gender is not None,
            age is not None,
            city not in (None, ""),
        )
    )
    watched_changed = any(
        (
            not same_ntrp(user.ntrp, ntrp),
            style_mask != (user.style_mask or 0),
            (bio or None) != (user.bio or None),
            gender != user.gender,
            age != user.age,
        )
    )
    result = await session.execute(
        update(AppUser)
        .where(AppUser.id == user.id, AppUser.version == user.version)
        .values(
            nickname=nickname,
            avatar_file_id=avatar,
            ntrp=ntrp,
            gender=gender,
            age=age,
            city=city,
            style_mask=style_mask,
            bio=bio,
            profile_completed=completed,
            ntrp_update_time=ntrp_update_time,
            version=user.version + 1,
        )
    )
    if result.rowcount != 1:
        await session.rollback()
        raise BizError(40904, "状态已变化，请刷新后重试")
    if watched_changed:
        delete_cache = (
            "DELETE FROM llm_match_cache WHERE publisher_id = :uid OR candidate_id = :uid"
        )
        await session.execute(text(delete_cache), {"uid": user.id})
    await session.commit()
    await session.refresh(user)
    return await build_profile(session, user)


def _present[T](field: str, value: T | None) -> T:
    if value is None:
        raise BizError(
            400,
            "参数错误",
            {"errors": [{"loc": [field], "msg": "不能为空"}]},
        )
    return value


def _claim_ntrp_change(previous: datetime | None, clock: Clock) -> datetime:
    now = clock.now()
    if previous is not None:
        next_at = add_months(previous, 1)
        if now < next_at:
            raise BizError(
                40301,
                "每月仅可修改一次",
                {"nextEditableAt": format_shanghai(next_at)},
            )
    return now


async def _active_request_id(session: AsyncSession, user_id: int) -> str | None:
    result = await session.execute(
        text(
            "SELECT id FROM match_request "
            "WHERE publisher_id = :uid AND status IN (1, 2) AND is_deleted = 0 "
            "ORDER BY id DESC LIMIT 1"
        ),
        {"uid": user_id},
    )
    value = result.scalar_one_or_none()
    if value is None:
        return None
    return str(value)
