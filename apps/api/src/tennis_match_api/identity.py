from collections.abc import Mapping
from dataclasses import dataclass

from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError

_UNTRUSTED = "缺少或不可信的微信身份"


@dataclass(frozen=True)
class WxIdentity:
    openid: str
    unionid: str | None
    appid: str | None
    source: str


def _header(headers: Mapping[str, str], name: str) -> str:
    return (headers.get(name) or headers.get(name.upper()) or "").strip()


def resolve_identity(headers: Mapping[str, str], settings: Settings) -> WxIdentity:
    if settings.auth_mode == "dev":
        openid = _header(headers, "x-dev-openid")
        if not openid:
            raise BizError(401, _UNTRUSTED)
        return WxIdentity(openid=openid, unionid=None, appid=None, source="dev")

    if _header(headers, "x-wx-from-openid") or _header(headers, "x-wx-from-appid"):
        raise BizError(401, _UNTRUSTED)
    source = _header(headers, "x-wx-source")
    openid = _header(headers, "x-wx-openid")
    if not source or not openid:
        raise BizError(401, _UNTRUSTED)
    appid = _header(headers, "x-wx-appid")
    if appid != settings.wechat_appid:
        raise BizError(401, _UNTRUSTED)
    if settings.cbr_env_id is not None:
        if _header(headers, "x-wx-env") != settings.cbr_env_id:
            raise BizError(401, _UNTRUSTED)
    unionid = _header(headers, "x-wx-unionid") or None
    return WxIdentity(openid=openid, unionid=unionid, appid=appid, source=source)
