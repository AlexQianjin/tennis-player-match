import asyncio
import os
from uuid import uuid4

from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from tests.helpers import complete_profile, wx_headers

from tennis_match_api.config import get_settings
from tennis_match_api.db import get_sessionmaker
from tennis_match_api.main import create_app


async def test_missing_source_or_openid_is_401(client) -> None:
    missing_source = {
        "X-WX-OPENID": "openid-1",
        "X-WX-APPID": "wx-test",
        "X-WX-ENV": "test-env",
    }
    missing_openid = {
        "X-WX-SOURCE": "wx_devtools",
        "X-WX-APPID": "wx-test",
        "X-WX-ENV": "test-env",
    }
    for headers in (missing_source, missing_openid):
        response = await client.post("/api/v1/auth/login", headers=headers)
        assert response.status_code == 401
        assert response.json()["code"] == 401


async def test_env_mismatch_and_from_openid_are_401(client) -> None:
    env_mismatch = wx_headers("openid-env")
    env_mismatch["X-WX-ENV"] = "other-env"
    reused = wx_headers("openid-from", **{"X-WX-FROM-OPENID": "other"})
    for headers in (env_mismatch, reused):
        response = await client.post("/api/v1/auth/login", headers=headers)
        assert response.status_code == 401
        assert response.json()["code"] == 401


async def test_dev_header_does_not_select_the_user_in_wxcloud_mode(client) -> None:
    openid = f"wx-{uuid4().hex}"
    headers = wx_headers(openid, **{"X-Dev-Openid": "dev_user_1"})
    first = await client.post("/api/v1/auth/login", headers=headers)
    assert first.status_code == 200
    second = await client.post("/api/v1/auth/login", headers=wx_headers(openid))
    assert second.status_code == 200
    assert first.json()["data"]["userInfo"]["id"] == second.json()["data"]["userInfo"]["id"]
    ignored = await client.post("/api/v1/auth/login", headers={"X-Dev-Openid": openid})
    assert ignored.status_code == 401


async def test_new_user_then_completed_user_login_flag(client) -> None:
    openid = f"user-{uuid4().hex}"
    created = await client.post("/api/v1/auth/login", headers=wx_headers(openid))
    assert created.status_code == 200
    body = created.json()
    assert body["data"]["isNewUser"] is True
    assert body["data"]["userInfo"]["profileCompleted"] is False
    assert body["data"]["userInfo"]["ntrpUpdateTime"] is None

    saved = await client.post(
        "/api/v1/user/profile",
        headers=wx_headers(openid),
        json=complete_profile(),
    )
    assert saved.status_code == 200
    assert saved.json()["data"]["profileCompleted"] is True

    again = await client.post("/api/v1/auth/login", headers=wx_headers(openid))
    assert again.status_code == 200
    assert again.json()["data"]["isNewUser"] is False


async def test_disabled_user_is_403(client) -> None:
    openid = f"disabled-{uuid4().hex}"
    created = await client.post("/api/v1/auth/login", headers=wx_headers(openid))
    assert created.status_code == 200
    factory = get_sessionmaker()
    async with factory() as session:
        await session.execute(
            text("UPDATE app_user SET is_deleted = 1 WHERE openid = :openid"),
            {"openid": openid},
        )
        await session.commit()
    blocked = await client.post("/api/v1/auth/login", headers=wx_headers(openid))
    assert blocked.status_code == 403
    assert blocked.json()["code"] == 403
    assert blocked.json()["message"] == "账号已停用"


async def test_concurrent_first_login_creates_one_user(client) -> None:
    openid = f"race-{uuid4().hex}"
    headers = wx_headers(openid)

    async def once() -> tuple[int, str | None]:
        response = await client.post("/api/v1/auth/login", headers=headers)
        data = response.json()["data"] if response.status_code == 200 else None
        user_id = data["userInfo"]["id"] if data else None
        return response.status_code, user_id

    results = await asyncio.gather(*(once() for _ in range(8)))
    assert [status for status, _ in results] == [200] * 8
    assert len({user_id for _, user_id in results}) == 1


async def test_dev_mode_uses_x_dev_openid_only() -> None:
    previous_auth = os.environ.get("AUTH_MODE")
    previous_app = os.environ.get("APP_ENV")
    os.environ["AUTH_MODE"] = "dev"
    os.environ["APP_ENV"] = "dev"
    get_settings.cache_clear()
    try:
        app = create_app()
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            openid = f"dev-{uuid4().hex}"
            ok = await http.post("/api/v1/auth/login", headers={"X-Dev-Openid": openid})
            assert ok.status_code == 200
            assert ok.json()["data"]["isNewUser"] is True
            rejected = await http.post("/api/v1/auth/login", headers=wx_headers(openid))
            assert rejected.status_code == 401
    finally:
        if previous_auth is None:
            os.environ.pop("AUTH_MODE", None)
        else:
            os.environ["AUTH_MODE"] = previous_auth
        if previous_app is None:
            os.environ.pop("APP_ENV", None)
        else:
            os.environ["APP_ENV"] = previous_app
        get_settings.cache_clear()
