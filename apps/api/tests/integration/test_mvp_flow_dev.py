"""Dev-header walkthrough of the mini program's MVP flow.

The http transport sends ``X-Dev-Openid``. Credit changes only after a participant
submits ratings for a completed match: arrival itself does not increment
``confirm_count``, and ``credit_score = max(confirm_count - cancel_count, 0)``.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient
from tests.helpers import complete_profile
from tests.integration.test_llm_recommend import FakeLLM
from tests.integration.test_match_http import _court, _publish, _use_clock

from tennis_match_api.config import get_settings
from tennis_match_api.main import create_app
from tennis_match_api.services.lifecycle_service import auto_cancel_unconfirmed, expire_unfilled
from tennis_match_api.services.llm.client import get_llm_client


def _dev(openid: str) -> dict[str, str]:
    return {"X-Dev-Openid": openid}


def _utc(iso: str) -> datetime:
    parsed = datetime.fromisoformat(iso)
    if parsed.tzinfo is None:
        return parsed
    return parsed.astimezone(UTC).replace(tzinfo=None)


def _ok(response) -> dict[str, object]:
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["code"] == 0, payload
    data = payload["data"]
    assert isinstance(data, dict)
    return data


def _err(response, code: int) -> dict[str, object]:
    expected = code if code < 1000 else code // 100
    assert response.status_code == expected, response.text
    payload = response.json()
    assert payload["code"] == code, payload
    assert isinstance(payload, dict)
    return payload


@pytest.fixture
def dev_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("LLM_ENABLED", "false")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    get_settings.cache_clear()
    application = create_app()
    yield application
    get_settings.cache_clear()


@pytest.fixture
async def dev_client(dev_app):
    transport = ASGITransport(app=dev_app)
    async with AsyncClient(transport=transport, base_url="http://test") as http:
        yield http


async def _login(client: AsyncClient, openid: str) -> dict[str, object]:
    return _ok(await client.post("/api/v1/auth/login", headers=_dev(openid)))


async def _profile(client: AsyncClient, openid: str) -> dict[str, object]:
    return _ok(await client.get("/api/v1/user/profile", headers=_dev(openid)))


async def _counts(client: AsyncClient, openid: str) -> tuple[int, int, int]:
    data = await _profile(client, openid)
    confirm = int(data["confirmCount"])  # type: ignore[arg-type]
    cancel = int(data["cancelCount"])  # type: ignore[arg-type]
    credit = int(data["creditScore"])  # type: ignore[arg-type]
    assert credit == max(confirm - cancel, 0)
    return confirm, cancel, credit


async def _publish_match(
    client: AsyncClient, openid: str, court_id: str, **overrides: object
) -> str:
    created = await client.post(
        "/api/v1/match/publish",
        headers=_dev(openid),
        json=_publish(court_id, **overrides),
    )
    return str(_ok(created)["id"])


async def _apply(client: AsyncClient, openid: str, request_id: str) -> str:
    applied = await client.post(
        "/api/v1/match/apply",
        headers=_dev(openid),
        json={"requestId": request_id},
    )
    return str(_ok(applied)["applicationId"])


async def _agree(client: AsyncClient, openid: str, application_id: str) -> dict[str, object]:
    handled = await client.post(
        "/api/v1/match/handle",
        headers=_dev(openid),
        json={"applicationId": application_id, "action": "agree"},
    )
    return _ok(handled)


async def test_dev_openid_mvp_flow(dev_client: AsyncClient, dev_app) -> None:
    clock = _use_clock(dev_app, datetime(2026, 11, 1, 1, 0, 0))
    host, bella, chen = (f"dev-{uuid4().hex}" for _ in range(3))
    court_id = await _court()

    missing = await dev_client.post("/api/v1/auth/login")
    _err(missing, 401)
    blank = await dev_client.post("/api/v1/auth/login", headers={"X-Dev-Openid": "  "})
    _err(blank, 401)
    wx_only = await dev_client.post(
        "/api/v1/auth/login",
        headers={
            "X-WX-SOURCE": "wx_devtools",
            "X-WX-OPENID": host,
            "X-WX-APPID": "wx-test",
            "X-WX-ENV": "test-env",
        },
    )
    _err(wx_only, 401)

    first = await _login(dev_client, host)
    assert first["isNewUser"] is True
    user_info = first["userInfo"]
    assert isinstance(user_info, dict)
    assert user_info["profileCompleted"] is False
    blocked = await dev_client.post(
        "/api/v1/match/publish",
        headers=_dev(host),
        json=_publish(court_id, matchType="singles", slotsNeeded=1),
    )
    _err(blocked, 40001)

    for openid, gender, nickname in (
        (host, "male", "主场"),
        (bella, "female", "小球"),
        (chen, "male", "陈"),
    ):
        await _login(dev_client, openid)
        saved = await dev_client.post(
            "/api/v1/user/profile",
            headers=_dev(openid),
            json=complete_profile(gender=gender, nickname=nickname, ntrp=3.5),
        )
        assert _ok(saved)["profileCompleted"] is True
    again = await _login(dev_client, host)
    assert again["isNewUser"] is False

    gendered = await _publish_match(
        dev_client,
        bella,
        court_id,
        matchType="singles",
        slotsNeeded=1,
        genderPref="female",
        date="2026-11-02",
    )
    for openid in (chen, host):
        unfit = await dev_client.post(
            "/api/v1/match/apply",
            headers=_dev(openid),
            json={"requestId": gendered},
        )
        _err(unfit, 40303)
    preview = _ok(
        await dev_client.get(
            "/api/v1/match/cancel/preview",
            headers=_dev(bella),
            params={"requestId": gendered},
        )
    )
    assert preview == {"cancelCounted": False, "effect": "cancel_all"}
    cancelled = _ok(
        await dev_client.post(
            "/api/v1/match/cancel",
            headers=_dev(bella),
            json={"requestId": gendered},
        )
    )
    assert cancelled["cancelCounted"] is False
    assert (await _counts(dev_client, bella))[1] == 0

    doubles = await _publish_match(
        dev_client, host, court_id, matchType="doubles", slotsNeeded=2, date="2026-11-02"
    )
    second = await dev_client.post(
        "/api/v1/match/publish",
        headers=_dev(host),
        json=_publish(court_id, matchType="singles", slotsNeeded=1, date="2026-11-02"),
    )
    assert _err(second, 40901)["message"] == "您已有一个进行中的约球，请先完成或取消"

    bella_listing = await _publish_match(
        dev_client, bella, court_id, matchType="singles", slotsNeeded=1, date="2026-11-02"
    )
    first_page = _ok(
        await dev_client.get(
            "/api/v1/match/recommend",
            headers=_dev(chen),
            params={"city": "武汉", "courtId": court_id, "page": 1, "pageSize": 1},
        )
    )
    assert first_page["llmApplied"] is False
    assert first_page["page"] == 1
    assert first_page["pageSize"] == 1
    assert first_page["total"] == 2
    assert first_page["hasMore"] is True
    listed = first_page["list"]
    assert isinstance(listed, list) and len(listed) == 1
    assert listed[0]["llmScore"] is None
    assert listed[0]["finalScore"] is None
    assert isinstance(listed[0]["ruleScore"], (int, float))
    second_page = _ok(
        await dev_client.get(
            "/api/v1/match/recommend",
            headers=_dev(chen),
            params={"city": "武汉", "courtId": court_id, "page": 2, "pageSize": 1},
        )
    )
    seen = {listed[0]["id"], second_page["list"][0]["id"]}  # type: ignore[index]
    assert seen == {doubles, bella_listing}
    males = _ok(
        await dev_client.get(
            "/api/v1/match/recommend",
            headers=_dev(chen),
            params={"city": "武汉", "courtId": court_id, "gender": "male", "pageSize": 10},
        )
    )
    assert [row["id"] for row in males["list"]] == [doubles]  # type: ignore[index]
    empty_slot = _ok(
        await dev_client.get(
            "/api/v1/match/recommend",
            headers=_dev(chen),
            params={"city": "武汉", "courtId": court_id, "timeSlot": "09:00-11:00"},
        )
    )
    assert empty_slot["list"] == []
    _ok(
        await dev_client.post(
            "/api/v1/match/cancel",
            headers=_dev(bella),
            json={"requestId": bella_listing},
        )
    )
    assert (await _counts(dev_client, bella))[1] == 0

    chen_app = await _apply(dev_client, chen, doubles)
    duplicate = await dev_client.post(
        "/api/v1/match/apply",
        headers=_dev(chen),
        json={"requestId": doubles},
    )
    assert _err(duplicate, 40902)["message"] == "您已申请过该约球"
    own = await dev_client.post(
        "/api/v1/match/apply",
        headers=_dev(host),
        json={"requestId": doubles},
    )
    _err(own, 40304)
    bella_app = await _apply(dev_client, bella, doubles)
    outsider = await dev_client.post(
        "/api/v1/match/handle",
        headers=_dev(chen),
        json={"applicationId": bella_app, "action": "reject"},
    )
    _err(outsider, 403)
    queued = _ok(
        await dev_client.get(
            "/api/v1/match/applications",
            headers=_dev(host),
            params={"requestId": doubles},
        )
    )
    assert {row["applicationId"] for row in queued["list"]} == {chen_app, bella_app}  # type: ignore[index]

    first_agree = await _agree(dev_client, host, bella_app)
    request = first_agree["request"]
    assert isinstance(request, dict)
    assert request["status"] == "pending"
    assert request["filledCount"] == 1
    pending_tab = _ok(
        await dev_client.get("/api/v1/match/my", headers=_dev(host), params={"tab": "pending"})
    )
    pending_row = next(row for row in pending_tab["list"] if row["id"] == doubles)  # type: ignore[index]
    assert pending_row["tab"] == "pending"
    assert pending_row["pendingApplicationCount"] == 1

    filled = await _agree(dev_client, host, chen_app)
    matched = filled["request"]
    assert isinstance(matched, dict)
    assert matched["status"] == "matched"
    assert matched["filledCount"] == 2
    detail = _ok(await dev_client.get(f"/api/v1/match/detail/{doubles}", headers=_dev(host)))
    participants = detail["participants"]
    assert isinstance(participants, list) and len(participants) == 3
    confirmed = _ok(
        await dev_client.get("/api/v1/match/my", headers=_dev(host), params={"tab": "confirmed"})
    )
    assert doubles in {row["id"] for row in confirmed["list"]}  # type: ignore[index]
    applied = _ok(
        await dev_client.get(
            "/api/v1/match/my",
            headers=_dev(bella),
            params={"type": "applied", "page": 1, "pageSize": 10},
        )
    )
    assert doubles in {row["id"] for row in applied["list"]}  # type: ignore[index]
    assert applied["hasMore"] is False
    partner_list = _ok(
        await dev_client.get("/api/v1/match/my", headers=_dev(chen), params={"type": "matched"})
    )
    assert doubles in {row["id"] for row in partner_list["list"]}  # type: ignore[index]
    late_withdraw = await dev_client.post(
        "/api/v1/match/application/withdraw",
        headers=_dev(chen),
        json={"applicationId": chen_app},
    )
    _err(late_withdraw, 40904)

    start = _utc(str(detail["arriveWindow"]["from"]))  # type: ignore[index]
    deadline = _utc(str(detail["arriveWindow"]["to"]))  # type: ignore[index]
    assert deadline - start == timedelta(hours=24)
    clock.moment = start - timedelta(minutes=1)
    early = await dev_client.post(
        "/api/v1/match/arrive", headers=_dev(host), json={"requestId": doubles}
    )
    _err(early, 40302)
    too_soon = await dev_client.post(
        "/api/v1/match/rate",
        headers=_dev(host),
        json={"requestId": doubles, "ratings": [{"rateeId": "1", "score": 5}]},
    )
    _err(too_soon, 40904)
    assert await _counts(dev_client, host) == (0, 0, 0)

    clock.moment = start
    ids = {
        "host": str((await _profile(dev_client, host))["id"]),
        "bella": str((await _profile(dev_client, bella))["id"]),
        "chen": str((await _profile(dev_client, chen))["id"]),
    }
    for openid, done in ((host, False), (bella, False), (chen, True)):
        arrived = _ok(
            await dev_client.post(
                "/api/v1/match/arrive",
                headers=_dev(openid),
                json={"requestId": doubles},
            )
        )
        assert arrived["allArrived"] is done
        assert arrived["request"]["status"] == ("completed" if done else "matched")  # type: ignore[index]
    for openid in (host, bella, chen):
        assert (await _counts(dev_client, openid))[0] == 0

    partial = await dev_client.post(
        "/api/v1/match/rate",
        headers=_dev(host),
        json={"requestId": doubles, "ratings": [{"rateeId": ids["bella"], "score": 5}]},
    )
    _err(partial, 400)
    includes_self = await dev_client.post(
        "/api/v1/match/rate",
        headers=_dev(host),
        json={
            "requestId": doubles,
            "ratings": [
                {"rateeId": ids["host"], "score": 5},
                {"rateeId": ids["bella"], "score": 5},
                {"rateeId": ids["chen"], "score": 5},
            ],
        },
    )
    _err(includes_self, 400)
    rated = _ok(
        await dev_client.post(
            "/api/v1/match/rate",
            headers=_dev(host),
            json={
                "requestId": doubles,
                "ratings": [
                    {"rateeId": ids["bella"], "score": 5},
                    {"rateeId": ids["chen"], "score": 4},
                ],
            },
        )
    )
    assert rated["creditDelta"] == 1
    assert rated["myCreditScore"] == 1
    _ok(
        await dev_client.post(
            "/api/v1/match/rate",
            headers=_dev(bella),
            json={
                "requestId": doubles,
                "ratings": [
                    {"rateeId": ids["host"], "score": 3},
                    {"rateeId": ids["chen"], "score": 5},
                ],
            },
        )
    )
    _ok(
        await dev_client.post(
            "/api/v1/match/rate",
            headers=_dev(chen),
            json={
                "requestId": doubles,
                "ratings": [
                    {"rateeId": ids["host"], "score": 5},
                    {"rateeId": ids["bella"], "score": 4},
                ],
            },
        )
    )
    assert await _counts(dev_client, host) == (1, 0, 1)
    assert await _counts(dev_client, bella) == (1, 0, 1)
    assert await _counts(dev_client, chen) == (1, 0, 1)
    host_profile = await _profile(dev_client, host)
    bella_profile = await _profile(dev_client, bella)
    chen_profile = await _profile(dev_client, chen)
    assert host_profile["avgRating"] == 4
    assert bella_profile["avgRating"] == 4.5
    assert chen_profile["avgRating"] == 4.5
    assert host_profile["ratingCount"] == 2
    duplicate_rate = await dev_client.post(
        "/api/v1/match/rate",
        headers=_dev(host),
        json={
            "requestId": doubles,
            "ratings": [
                {"rateeId": ids["bella"], "score": 1},
                {"rateeId": ids["chen"], "score": 1},
            ],
        },
    )
    _err(duplicate_rate, 40905)

    counted = await _publish_match(
        dev_client, host, court_id, matchType="singles", slotsNeeded=1, date="2026-11-03"
    )
    counted_app = await _apply(dev_client, bella, counted)
    agreed = await _agree(dev_client, host, counted_app)
    assert agreed["request"]["status"] == "matched"  # type: ignore[index]
    counted_preview = _ok(
        await dev_client.get(
            "/api/v1/match/cancel/preview",
            headers=_dev(host),
            params={"requestId": counted},
        )
    )
    assert counted_preview["cancelCounted"] is True
    closed = _ok(
        await dev_client.post(
            "/api/v1/match/cancel",
            headers=_dev(host),
            json={"requestId": counted, "reason": "临时有事"},
        )
    )
    assert closed["cancelCounted"] is True
    assert closed["request"]["status"] == "cancelled"  # type: ignore[index]
    assert await _counts(dev_client, host) == (1, 1, 0)
    assert (await _counts(dev_client, bella))[1] == 0

    expiring = await _publish_match(
        dev_client, bella, court_id, matchType="singles", slotsNeeded=1, date="2026-11-04"
    )
    expiring_app = await _apply(dev_client, chen, expiring)
    assert (await _agree(dev_client, bella, expiring_app))["request"]["status"] == "matched"  # type: ignore[index]
    window = _ok(await dev_client.get(f"/api/v1/match/detail/{expiring}", headers=_dev(bella)))
    expire_start = _utc(str(window["arriveWindow"]["from"]))  # type: ignore[index]
    expire_deadline = _utc(str(window["arriveWindow"]["to"]))  # type: ignore[index]
    clock.moment = expire_start
    one_side = _ok(
        await dev_client.post(
            "/api/v1/match/arrive",
            headers=_dev(chen),
            json={"requestId": expiring},
        )
    )
    assert one_side["allArrived"] is False
    assert (await _counts(dev_client, chen))[0] == 1
    clock.moment = expire_deadline - timedelta(seconds=1)
    await auto_cancel_unconfirmed(clock)
    assert (
        _ok(await dev_client.get(f"/api/v1/match/detail/{expiring}", headers=_dev(bella)))["status"]
        == "matched"
    )
    clock.moment = expire_deadline
    await auto_cancel_unconfirmed(clock)
    expired = _ok(await dev_client.get(f"/api/v1/match/detail/{expiring}", headers=_dev(bella)))
    assert expired["status"] == "cancelled"
    assert expired["cancelReason"] == 5
    assert await _counts(dev_client, bella) == (1, 0, 1)
    assert await _counts(dev_client, chen) == (1, 0, 1)
    after_window = await dev_client.post(
        "/api/v1/match/arrive",
        headers=_dev(bella),
        json={"requestId": expiring},
    )
    _err(after_window, 403)

    unfilled = await _publish_match(
        dev_client, host, court_id, matchType="singles", slotsNeeded=1, date="2026-11-06"
    )
    unfilled_window = _ok(
        await dev_client.get(f"/api/v1/match/detail/{unfilled}", headers=_dev(host))
    )
    clock.moment = _utc(str(unfilled_window["arriveWindow"]["from"]))  # type: ignore[index]
    await expire_unfilled(clock)
    emptied = _ok(await dev_client.get(f"/api/v1/match/detail/{unfilled}", headers=_dev(host)))
    assert emptied["status"] == "cancelled"
    assert emptied["cancelReason"] == 4
    assert await _counts(dev_client, host) == (1, 1, 0)

    raised = _ok(
        await dev_client.post(
            "/api/v1/user/profile",
            headers=_dev(chen),
            json={"ntrp": 4.0},
        )
    )
    assert raised["ntrp"] == 4.0
    assert raised["ntrpUpdateTime"] is not None
    cooled = await dev_client.post(
        "/api/v1/user/profile",
        headers=_dev(chen),
        json={"ntrp": 3.0},
    )
    cooldown = _err(cooled, 40301)
    assert cooldown["message"] == "每月仅可修改一次"
    data = cooldown["data"]
    assert isinstance(data, dict) and isinstance(data["nextEditableAt"], str)
    assert (await _profile(dev_client, chen))["ntrp"] == 4.0


@pytest.fixture
def dev_llm_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("AUTH_MODE", "dev")
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AI_MODEL_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("AI_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL_NAME", "fake-model")
    monkeypatch.setenv("SCHEDULER_ENABLED", "false")
    get_settings.cache_clear()
    application = create_app()
    yield application
    get_settings.cache_clear()


async def test_dev_recommend_falls_back_when_llm_fails(dev_llm_app) -> None:
    fake = FakeLLM("throw")
    _use_clock(dev_llm_app, datetime(2026, 11, 1, 1, 0, 0))
    dev_llm_app.dependency_overrides[get_llm_client] = lambda: fake
    transport = ASGITransport(app=dev_llm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        host, viewer = (f"dev-llm-{uuid4().hex}" for _ in range(2))
        court_id = await _court()
        for openid in (host, viewer):
            assert (await _login(client, openid))["isNewUser"] is True
            _ok(
                await client.post(
                    "/api/v1/user/profile",
                    headers=_dev(openid),
                    json=complete_profile(ntrp=3.5, gender="male"),
                )
            )
        request_id = await _publish_match(client, host, court_id, date="2026-11-02")
        page = _ok(
            await client.get(
                "/api/v1/match/recommend",
                headers=_dev(viewer),
                params={"city": "武汉", "courtId": court_id},
            )
        )
    assert fake.calls == 1
    assert page["llmApplied"] is False
    rows = page["list"]
    assert isinstance(rows, list)
    match = next(row for row in rows if row["id"] == request_id)
    assert match["llmScore"] is None
    assert match["finalScore"] is None
    assert isinstance(match["ruleScore"], (int, float))
