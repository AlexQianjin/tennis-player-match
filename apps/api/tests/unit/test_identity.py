import pytest
from pydantic import SecretStr, ValidationError

from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError
from tennis_match_api.identity import resolve_identity


def _settings(**overrides: object) -> Settings:
    payload: dict[str, object] = {
        "app_env": "test",
        "auth_mode": "wxcloud",
        "mysql_address": "127.0.0.1:3306",
        "mysql_username": "tennis",
        "mysql_password": SecretStr("tennis"),
        "wechat_appid": "wx-test",
        "cbr_env_id": "test-env",
    }
    payload.update(overrides)
    return Settings(**payload)  # type: ignore[arg-type]


def test_wxcloud_requires_source_and_openid() -> None:
    with pytest.raises(BizError) as caught:
        resolve_identity({"x-dev-openid": "dev_user_1"}, _settings())
    assert caught.value.code == 401
    assert caught.value.http_status == 401


def test_wxcloud_rejects_appid_or_env_mismatch() -> None:
    headers = {
        "x-wx-source": "wx_devtools",
        "x-wx-openid": "openid-1",
        "x-wx-appid": "other-app",
        "x-wx-env": "test-env",
    }
    with pytest.raises(BizError) as caught:
        resolve_identity(headers, _settings())
    assert caught.value.code == 401

    headers["x-wx-appid"] = "wx-test"
    headers["x-wx-env"] = "other-env"
    with pytest.raises(BizError) as caught:
        resolve_identity(headers, _settings())
    assert caught.value.code == 401


def test_wxcloud_rejects_resource_reuse_headers() -> None:
    headers = {
        "x-wx-source": "wx_devtools",
        "x-wx-openid": "openid-1",
        "x-wx-appid": "wx-test",
        "x-wx-env": "test-env",
        "x-wx-from-openid": "other",
    }
    with pytest.raises(BizError) as caught:
        resolve_identity(headers, _settings())
    assert caught.value.code == 401


def test_wxcloud_accepts_gateway_headers() -> None:
    identity = resolve_identity(
        {
            "x-wx-source": "wx_devtools",
            "x-wx-openid": "openid-1",
            "x-wx-appid": "wx-test",
            "x-wx-env": "test-env",
            "x-wx-unionid": "union-1",
        },
        _settings(),
    )
    assert identity.openid == "openid-1"
    assert identity.unionid == "union-1"
    assert identity.source == "wx_devtools"


def test_dev_mode_reads_x_dev_openid_only_outside_prod() -> None:
    identity = resolve_identity(
        {"x-dev-openid": " dev_user_1 "},
        _settings(app_env="dev", auth_mode="dev", cbr_env_id=None),
    )
    assert identity.openid == "dev_user_1"
    assert identity.source == "dev"
    with pytest.raises(BizError):
        resolve_identity({}, _settings(app_env="dev", auth_mode="dev", cbr_env_id=None))


def test_prod_rejects_dev_auth_mode() -> None:
    with pytest.raises(ValidationError):
        _settings(app_env="prod", auth_mode="dev")


def test_mysql_address_must_include_port() -> None:
    with pytest.raises(ValidationError):
        _settings(mysql_address="localhost")
