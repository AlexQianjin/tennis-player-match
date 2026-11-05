import csv
from datetime import datetime
from pathlib import Path

import pytest
from pydantic import SecretStr, ValidationError

from tennis_match_api.config import Settings
from tennis_match_api.errors import BizError
from tennis_match_api.models import AppUser
from tennis_match_api.ntrp import parse_ntrp
from tennis_match_api.schemas import ProfileUpdate
from tennis_match_api.scripts.seed import validate_court_rows
from tennis_match_api.services.auth_service import IdentityCache
from tennis_match_api.services.avatar import validate_avatar_file_id
from tennis_match_api.services.profile_service import ensure_profile_completed
from tennis_match_api.timefmt import add_months, format_shanghai

_CSV = Path(__file__).resolve().parents[2] / "seed" / "courts_wuhan.csv"


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


def test_ntrp_grid_rejects_off_step_and_out_of_range() -> None:
    assert parse_ntrp(3.5) == parse_ntrp("3.5")
    assert parse_ntrp(1) == parse_ntrp("1.0")
    assert parse_ntrp(7) == parse_ntrp("7.0")
    for bad in (3.3, 7.5, 0.5, "nope", True):
        with pytest.raises(ValueError):
            parse_ntrp(bad)


def test_profile_update_schema_rejects_bad_ntrp_before_the_database() -> None:
    with pytest.raises(ValidationError):
        ProfileUpdate(ntrp=3.3)
    with pytest.raises(ValidationError):
        ProfileUpdate(ntrp=7.5)
    with pytest.raises(ValidationError):
        ProfileUpdate(nickname="名" * 21)
    with pytest.raises(ValidationError):
        ProfileUpdate(age=5)
    with pytest.raises(ValidationError):
        ProfileUpdate(gender="other")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        ProfileUpdate(style=["smash"])  # type: ignore[list-item]


def test_add_months_clamps_short_months() -> None:
    assert add_months(datetime(2024, 1, 31, 2, 0), 1) == datetime(2024, 2, 29, 2, 0)
    assert add_months(datetime(2026, 1, 31, 2, 0), 1) == datetime(2026, 2, 28, 2, 0)
    assert format_shanghai(datetime(2026, 2, 15, 2, 0)) == "2026-02-15T10:00:00+08:00"


def test_avatar_file_id_shape() -> None:
    settings = _settings()
    validate_avatar_file_id("cloud://test-env.bucket/avatars/a.jpg", settings)
    dev = _settings(cbr_env_id=None)
    validate_avatar_file_id("cloud://dev.local/avatars/a.jpg", dev)
    for bad in (
        "https://example.com/a.jpg",
        "cloud://other-env.bucket/avatars/a.jpg",
        "cloud://test-env.bucket/photos/a.jpg",
        "cloud://test-env.bucket/avatars/../secret.jpg",
        "not-a-file-id",
    ):
        with pytest.raises(BizError) as caught:
            validate_avatar_file_id(bad, settings)
        assert caught.value.code == 40004
        assert caught.value.http_status == 400


def test_incomplete_profile_is_40001() -> None:
    user = AppUser(openid="dev_user", profile_completed=False)
    with pytest.raises(BizError) as caught:
        ensure_profile_completed(user)
    assert caught.value.code == 40001
    assert caught.value.message == "资料未完善，请先完善资料"
    ready = AppUser(openid="dev_user", profile_completed=True)
    ensure_profile_completed(ready)


def test_identity_cache_round_trip() -> None:
    cache = IdentityCache(ttl_seconds=60, max_size=2)
    cache.put("a", 1)
    cache.put("b", 2)
    assert cache.get("a") == 1
    cache.put("c", 3)
    assert cache.get("a") is None
    cache.invalidate("b")
    assert cache.get("b") is None


def test_wuhan_court_csv_is_public_venues_without_placeholder_flag() -> None:
    with _CSV.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert [row["name"] for row in rows] == [
        "武汉全民健身中心网球场",
        "汉江湾体育公园网球场",
        "武汉五环体育中心网球场",
        "毛坦公园网球场",
        "汉口文体中心网球场",
        "光谷国际网球中心",
        "好燃时刻智慧体育公园网球场",
    ]
    assert all(row["city"] == "武汉" for row in rows)
    assert [int(row["sort_order"]) for row in rows] == [10, 20, 30, 40, 50, 60, 70]
    assert all(row["is_active"] == "true" for row in rows)
    assert "TODO" not in _CSV.read_text(encoding="utf-8")
    coords = [(row["latitude"], row["longitude"]) for row in rows]
    assert coords[1] == ("30.585875", "114.201625")
    assert all(lat == "" and lng == "" for lat, lng in coords[:1] + coords[2:])
    validate_court_rows(rows, app_env="dev", allow_placeholder=False)
    validate_court_rows(rows, app_env="prod", allow_placeholder=False)


def test_placeholder_court_rows_still_need_the_flag() -> None:
    rows = [
        {
            "name": "TODO-球场名称-01",
            "city": "武汉",
            "district": "TODO-所在区",
            "address": "TODO-详细地址",
            "latitude": "",
            "longitude": "",
            "sort_order": "10",
            "is_active": "true",
        }
    ]
    with pytest.raises(SystemExit, match="allow-placeholder"):
        validate_court_rows(rows, app_env="dev", allow_placeholder=False)
    with pytest.raises(SystemExit, match="APP_ENV=prod"):
        validate_court_rows(rows, app_env="prod", allow_placeholder=True)
    validate_court_rows(rows, app_env="dev", allow_placeholder=True)
