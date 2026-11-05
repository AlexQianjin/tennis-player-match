from datetime import datetime
from uuid import uuid4

from tests.helpers import complete_profile, wx_headers

from tennis_match_api.clock import Clock, get_clock


class MutableClock(Clock):
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


async def _login(client, openid: str) -> None:
    response = await client.post("/api/v1/auth/login", headers=wx_headers(openid))
    assert response.status_code == 200


async def test_partial_update_stays_incomplete_until_required_fields_exist(client) -> None:
    openid = f"partial-{uuid4().hex}"
    await _login(client, openid)
    response = await client.post(
        "/api/v1/user/profile",
        headers=wx_headers(openid),
        json={"nickname": "小球员"},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["profileCompleted"] is False
    assert data["nickname"] == "小球员"
    assert data["missingFields"] == ["avatar", "ntrp", "gender", "age", "city"]

    empty = await client.patch("/api/v1/user/profile", headers=wx_headers(openid), json={})
    assert empty.status_code == 200
    assert empty.json()["data"]["nickname"] == "小球员"


async def test_invalid_ntrp_city_style_and_avatar(client) -> None:
    openid = f"invalid-{uuid4().hex}"
    await _login(client, openid)
    headers = wx_headers(openid)

    for payload in (
        {"ntrp": 3.3},
        {"ntrp": 7.5},
        {"city": "北京"},
        {"style": ["smash"]},
        {"gender": "other"},
        {"age": 5},
        {"nickname": "名" * 21},
        {"bio": "字" * 501},
    ):
        response = await client.post("/api/v1/user/profile", headers=headers, json=payload)
        assert response.status_code == 400, payload
        assert response.json()["code"] == 400

    bad_avatar = await client.post(
        "/api/v1/user/profile",
        headers=headers,
        json={"avatar": "cloud://other-env.bucket/avatars/a.jpg"},
    )
    assert bad_avatar.status_code == 400
    assert bad_avatar.json()["code"] == 40004
    wrong_path = await client.post(
        "/api/v1/user/profile",
        headers=headers,
        json={"avatar": "cloud://test-env.bucket/photos/a.jpg"},
    )
    assert wrong_path.status_code == 400
    assert wrong_path.json()["code"] == 40004


async def test_first_ntrp_is_free_and_the_next_change_inside_a_month_is_40301(client, app) -> None:
    clock = MutableClock(datetime(2026, 1, 15, 2, 0, 0))
    app.dependency_overrides[get_clock] = lambda: clock
    openid = f"ntrp-{uuid4().hex}"
    await _login(client, openid)
    headers = wx_headers(openid)

    created = await client.post("/api/v1/user/profile", headers=headers, json=complete_profile())
    assert created.status_code == 200
    created_body = created.json()["data"]
    assert created_body["profileCompleted"] is True
    assert created_body["ntrp"] == 3.5
    assert created_body["ntrpUpdateTime"] is None
    assert created_body["ntrpNextEditableAt"] is None
    assert created_body["style"] == ["doubles", "casual"]
    assert created_body["activeRequestId"] is None

    # The first correction is allowed and starts the one-month cooldown.
    corrected = await client.post(
        "/api/v1/user/profile",
        headers=headers,
        json={"ntrp": 4.0},
    )
    assert corrected.status_code == 200
    assert corrected.json()["data"]["ntrp"] == 4.0
    assert corrected.json()["data"]["ntrpUpdateTime"] == "2026-01-15T10:00:00+08:00"
    assert corrected.json()["data"]["ntrpNextEditableAt"] == "2026-02-15T10:00:00+08:00"

    same = await client.post("/api/v1/user/profile", headers=headers, json={"ntrp": 4.0})
    assert same.status_code == 200

    bio = await client.post("/api/v1/user/profile", headers=headers, json={"bio": "只改简介"})
    assert bio.status_code == 200
    assert bio.json()["data"]["bio"] == "只改简介"

    blocked = await client.post("/api/v1/user/profile", headers=headers, json={"ntrp": 4.5})
    assert blocked.status_code == 403
    blocked_body = blocked.json()
    assert blocked_body["code"] == 40301
    assert blocked_body["data"]["nextEditableAt"] == "2026-02-15T10:00:00+08:00"

    clock.moment = datetime(2026, 2, 15, 2, 0, 0)
    allowed = await client.patch("/api/v1/user/profile", headers=headers, json={"ntrp": 3.0})
    assert allowed.status_code == 200
    assert allowed.json()["data"]["ntrp"] == 3.0
    assert allowed.json()["data"]["ntrpUpdateTime"] == "2026-02-15T10:00:00+08:00"


async def test_public_profile_hides_private_fields(client) -> None:
    openid = f"public-{uuid4().hex}"
    await _login(client, openid)
    saved = await client.post(
        "/api/v1/user/profile",
        headers=wx_headers(openid),
        json=complete_profile(nickname="公开昵称"),
    )
    user_id = saved.json()["data"]["id"]
    public = await client.get(f"/api/v1/user/{user_id}/public", headers=wx_headers(openid))
    assert public.status_code == 200
    data = public.json()["data"]
    assert data["nickname"] == "公开昵称"
    assert data["city"] == "武汉"
    assert "confirmCount" not in data
    assert "openid" not in data
    assert "profileCompleted" not in data

    missing = await client.get("/api/v1/user/999999999/public", headers=wx_headers(openid))
    assert missing.status_code == 404
    assert missing.json()["code"] == 404
    anonymous = await client.get(f"/api/v1/user/{user_id}/public")
    assert anonymous.status_code == 401
