import asyncio
from datetime import datetime
from uuid import uuid4

from tests.helpers import complete_profile, wx_headers

from tennis_match_api.clock import Clock, get_clock
from tennis_match_api.db import get_sessionmaker
from tennis_match_api.models import Court


class MutableClock(Clock):
    def __init__(self, moment: datetime) -> None:
        self.moment = moment

    def now(self) -> datetime:
        return self.moment


def _use_clock(app, moment: datetime) -> MutableClock:
    clock = MutableClock(moment)
    app.dependency_overrides[get_clock] = lambda: clock
    return clock


async def _player(client, **profile: object) -> dict[str, str]:
    headers = wx_headers(f"m-{uuid4().hex}")
    created = await client.post("/api/v1/auth/login", headers=headers)
    assert created.status_code == 200
    saved = await client.post(
        "/api/v1/user/profile",
        headers=headers,
        json=complete_profile(**profile),
    )
    assert saved.status_code == 200, saved.text
    return headers


async def _court() -> str:
    factory = get_sessionmaker()
    async with factory() as session:
        court = Court(
            name=f"m-{uuid4().hex[:12]}",
            city="武汉",
            district="甲区",
            address="测试地址",
            sort_order=1,
            is_active=True,
        )
        session.add(court)
        await session.commit()
        await session.refresh(court)
        return str(court.id)


def _publish(court_id: str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "date": "2026-06-02",
        "timeSlot": "14:00-16:00",
        "courtId": court_id,
        "matchType": "doubles",
        "slotsNeeded": 3,
        "genderPref": "any",
    }
    body.update(overrides)
    return body


async def test_publish_validation_and_one_active_request(client, app) -> None:
    _use_clock(app, datetime(2026, 6, 1, 2, 0, 0))
    headers = await _player(client, ntrp=3.5, gender="male")
    court_id = await _court()

    past = await client.post(
        "/api/v1/match/publish",
        headers=headers,
        json=_publish(court_id, date="2026-05-01"),
    )
    assert past.status_code == 400
    assert past.json()["code"] == 40002

    bad_slot = await client.post(
        "/api/v1/match/publish",
        headers=headers,
        json=_publish(court_id, timeSlot="18:00-09:00"),
    )
    assert bad_slot.status_code == 400
    assert bad_slot.json()["code"] == 40002

    singles = await client.post(
        "/api/v1/match/publish",
        headers=headers,
        json=_publish(court_id, matchType="singles", slotsNeeded=2),
    )
    assert singles.status_code == 400
    assert singles.json()["code"] == 400
    for slots in (0, 4):
        doubles = await client.post(
            "/api/v1/match/publish",
            headers=headers,
            json=_publish(court_id, slotsNeeded=slots),
        )
        assert doubles.status_code == 400
        assert doubles.json()["code"] == 400

    missing_court = await client.post(
        "/api/v1/match/publish",
        headers=headers,
        json=_publish("999999"),
    )
    assert missing_court.status_code == 400
    assert missing_court.json()["code"] == 40003

    created = await client.post(
        "/api/v1/match/publish",
        headers=headers,
        json=_publish(
            court_id,
            matchType="singles",
            slotsNeeded=None,
            expectedNtrpMin=1.0,
            expectedNtrpMax=7.0,
        ),
    )
    assert created.status_code == 200, created.text
    data = created.json()["data"]
    assert data["matchType"] == "singles"
    assert data["slotsNeeded"] == 1
    assert data["status"] == "pending"
    assert data["expectedNtrpMin"] == 3.0
    assert data["expectedNtrpMax"] == 4.0
    assert data["participants"][0]["role"] == "publisher"
    assert "viewApplications" in data["availableActions"]
    assert data["myRole"] == "publisher"

    again = await client.post(
        "/api/v1/match/publish",
        headers=headers,
        json=_publish(court_id, matchType="singles", slotsNeeded=1),
    )
    assert again.status_code == 409
    assert again.json()["code"] == 40901

    incomplete = wx_headers(f"new-{uuid4().hex}")
    await client.post("/api/v1/auth/login", headers=incomplete)
    blocked = await client.post(
        "/api/v1/match/publish",
        headers=incomplete,
        json=_publish(court_id),
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == 40001


async def test_concurrent_publish_keeps_one_active_request(client, app) -> None:
    _use_clock(app, datetime(2026, 6, 1, 2, 0, 0))
    headers = await _player(client)
    court_id = await _court()

    async def once() -> int:
        response = await client.post(
            "/api/v1/match/publish",
            headers=headers,
            json=_publish(court_id, matchType="singles", slotsNeeded=1),
        )
        return response.status_code

    statuses = await asyncio.gather(once(), once())
    assert sorted(statuses) == [200, 409]


async def test_recommend_hard_filters_are_rules_only(client, app) -> None:
    _use_clock(app, datetime(2026, 6, 1, 2, 0, 0))
    publisher = await _player(client, ntrp=4.0, gender="male", nickname="发布")
    close = await _player(client, ntrp=3.5, gender="male", nickname="接近")
    far = await _player(client, ntrp=2.0, gender="male", nickname="差太远")
    female = await _player(client, ntrp=4.0, gender="female", nickname="女")
    court_id = await _court()
    created = await client.post(
        "/api/v1/match/publish",
        headers=publisher,
        json=_publish(
            court_id,
            expectedNtrpMin=4.0,
            expectedNtrpMax=4.5,
            genderPref="male",
        ),
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["data"]["id"]

    async def ids_for(headers: dict[str, str], **params: object) -> list[str]:
        response = await client.get(
            "/api/v1/match/recommend",
            headers=headers,
            params={"city": "武汉", "courtId": court_id, **params},
        )
        assert response.status_code == 200, response.text
        body = response.json()["data"]
        assert body["llmApplied"] is False
        return [item["id"] for item in body["list"]]

    visible = await client.get(
        "/api/v1/match/recommend",
        headers=close,
        params={"city": "武汉", "courtId": court_id, "date": "2026-06-03"},
    )
    assert visible.status_code == 200
    assert visible.json()["data"]["list"] == []

    matched = await client.get(
        "/api/v1/match/recommend",
        headers=await _player(client, ntrp=4.0, gender="male"),
        params={"city": "武汉", "courtId": court_id},
    )
    assert matched.status_code == 200
    item = next(row for row in matched.json()["data"]["list"] if row["id"] == request_id)
    assert item["llmScore"] is None
    assert item["finalScore"] is None
    assert item["ruleScore"] >= 0
    assert "apply" in item["availableActions"]

    assert request_id not in await ids_for(close)
    assert request_id not in await ids_for(far)
    assert request_id not in await ids_for(female)
    assert request_id not in await ids_for(publisher)

    clock = app.dependency_overrides[get_clock]()
    clock.moment = datetime(2026, 6, 2, 6, 0, 0)
    assert request_id not in await ids_for(await _player(client, ntrp=4.0, gender="male"))


async def test_doubles_fill_and_concurrent_last_slot(client, app) -> None:
    clock = _use_clock(app, datetime(2026, 6, 1, 2, 0, 0))
    publisher = await _player(client, ntrp=3.5, gender="male", nickname="局头")
    court_id = await _court()
    created = await client.post(
        "/api/v1/match/publish",
        headers=publisher,
        json=_publish(court_id, slotsNeeded=3),
    )
    assert created.status_code == 200, created.text
    request_id = created.json()["data"]["id"]
    applicants = [
        await _player(client, ntrp=3.5, gender="male", nickname=f"甲{i}") for i in range(4)
    ]
    application_ids: list[str] = []
    for headers in applicants:
        applied = await client.post(
            "/api/v1/match/apply",
            headers=headers,
            json={"requestId": request_id},
        )
        assert applied.status_code == 200, applied.text
        application_ids.append(applied.json()["data"]["applicationId"])

    own = await client.post(
        "/api/v1/match/apply",
        headers=publisher,
        json={"requestId": request_id},
    )
    assert own.status_code == 403
    assert own.json()["code"] == 40304

    stranger = await _player(client, ntrp=2.0, gender="male")
    unfit = await client.post(
        "/api/v1/match/apply",
        headers=stranger,
        json={"requestId": request_id},
    )
    assert unfit.status_code == 403
    assert unfit.json()["code"] == 40303

    duplicate = await client.post(
        "/api/v1/match/apply",
        headers=applicants[0],
        json={"requestId": request_id},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 40902

    outsider = await client.post(
        "/api/v1/match/handle",
        headers=applicants[0],
        json={"applicationId": application_ids[1], "action": "reject"},
    )
    assert outsider.status_code == 403
    assert outsider.json()["code"] == 403

    for application_id in application_ids[:2]:
        agreed = await client.post(
            "/api/v1/match/handle",
            headers=publisher,
            json={"applicationId": application_id, "action": "agree"},
        )
        assert agreed.status_code == 200, agreed.text
        assert agreed.json()["data"]["request"]["status"] == "pending"

    third = await client.post(
        "/api/v1/match/handle",
        headers=publisher,
        json={"applicationId": application_ids[2], "action": "agree"},
    )
    assert third.status_code == 200, third.text
    assert third.json()["data"]["request"]["status"] == "matched"
    assert third.json()["data"]["request"]["filledCount"] == 3
    listed = await client.get(
        "/api/v1/match/applications",
        headers=publisher,
        params={"requestId": request_id},
    )
    assert listed.status_code == 200
    by_id = {row["applicationId"]: row["status"] for row in listed.json()["data"]["list"]}
    assert by_id[application_ids[3]] == "rejected"

    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=publisher)
    assert detail.status_code == 200
    body = detail.json()["data"]
    assert body["pendingApplicationCount"] == 0
    assert len(body["participants"]) == 4
    hidden = await client.get(f"/api/v1/match/detail/{request_id}", headers=applicants[0])
    assert hidden.json()["data"]["pendingApplicationCount"] is None

    # A second match with one remaining slot: only one of two agrees succeeds.
    clock.moment = datetime(2026, 6, 1, 2, 0, 0)
    host = await _player(client, ntrp=3.0, gender="female", nickname="单名额")
    other_court = await _court()
    singles = await client.post(
        "/api/v1/match/publish",
        headers=host,
        json=_publish(other_court, matchType="doubles", slotsNeeded=1, genderPref="any"),
    )
    assert singles.status_code == 200, singles.text
    slot_id = singles.json()["data"]["id"]
    racers = [
        await _player(client, ntrp=3.0, gender="female", nickname="竞1"),
        await _player(client, ntrp=3.0, gender="female", nickname="竞2"),
    ]
    race_apps: list[str] = []
    for headers in racers:
        applied = await client.post(
            "/api/v1/match/apply",
            headers=headers,
            json={"requestId": slot_id},
        )
        assert applied.status_code == 200, applied.text
        race_apps.append(applied.json()["data"]["applicationId"])

    async def agree(application_id: str) -> int:
        response = await client.post(
            "/api/v1/match/handle",
            headers=host,
            json={"applicationId": application_id, "action": "agree"},
        )
        return response.json()["code"] if response.status_code != 200 else 0

    codes = await asyncio.gather(agree(race_apps[0]), agree(race_apps[1]))
    assert sorted(codes) == [0, 40903]
