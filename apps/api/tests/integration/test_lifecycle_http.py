import asyncio
from datetime import datetime, timedelta

from sqlalchemy import text
from tests.integration.test_match_http import _court, _player, _publish, _use_clock

from tennis_match_api.clock import get_clock
from tennis_match_api.db import connect_mysql, get_sessionmaker
from tennis_match_api.services.lifecycle_service import auto_cancel_unconfirmed, expire_unfilled
from tennis_match_api.services.scheduler import run_exclusive, startup_catchup


async def _match(client, app, publisher, court_id: str, **overrides: object) -> str:
    created = await client.post(
        "/api/v1/match/publish",
        headers=publisher,
        json=_publish(court_id, **overrides),
    )
    assert created.status_code == 200, created.text
    return created.json()["data"]["id"]


async def _agree(client, publisher, applicant, request_id: str) -> None:
    applied = await client.post(
        "/api/v1/match/apply",
        headers=applicant,
        json={"requestId": request_id},
    )
    assert applied.status_code == 200, applied.text
    agreed = await client.post(
        "/api/v1/match/handle",
        headers=publisher,
        json={"applicationId": applied.json()["data"]["applicationId"], "action": "agree"},
    )
    assert agreed.status_code == 200, agreed.text


async def _profile(client, headers: dict[str, str]) -> dict[str, object]:
    response = await client.get("/api/v1/user/profile", headers=headers)
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_cancel_rules_and_credit_counts(client, app) -> None:
    _use_clock(app, datetime(2026, 7, 1, 2, 0, 0))
    court_id = await _court()
    host = await _player(client, ntrp=3.5, gender="male", nickname="局头")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-07-02"
    )
    preview = await client.get(
        "/api/v1/match/cancel/preview",
        headers=host,
        params={"requestId": request_id},
    )
    assert preview.status_code == 200
    assert preview.json()["data"] == {"cancelCounted": False, "effect": "cancel_all"}
    cancelled = await client.post(
        "/api/v1/match/cancel",
        headers=host,
        json={"requestId": request_id},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["data"]["cancelCounted"] is False
    assert cancelled.json()["data"]["request"]["status"] == "cancelled"
    assert (await _profile(client, host))["cancelCount"] == 0

    host = await _player(client, ntrp=3.5, gender="male")
    partner = await _player(client, ntrp=3.5, gender="male")
    request_id = await _match(client, app, host, court_id, slotsNeeded=2, date="2026-07-02")
    await _agree(client, host, partner, request_id)
    left = await client.post(
        "/api/v1/match/cancel",
        headers=partner,
        json={"requestId": request_id},
    )
    assert left.status_code == 200, left.text
    assert left.json()["data"]["cancelCounted"] is False
    assert left.json()["data"]["request"]["status"] == "pending"
    assert left.json()["data"]["request"]["filledCount"] == 0
    assert (await _profile(client, partner))["cancelCount"] == 0

    host = await _player(client, ntrp=3.5, gender="female")
    partner = await _player(client, ntrp=3.5, gender="female")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-07-02"
    )
    await _agree(client, host, partner, request_id)
    reopened = await client.post(
        "/api/v1/match/cancel",
        headers=partner,
        json={"requestId": request_id},
    )
    assert reopened.status_code == 200, reopened.text
    assert reopened.json()["data"]["cancelCounted"] is True
    assert reopened.json()["data"]["request"]["status"] == "pending"
    assert (await _profile(client, partner))["cancelCount"] == 1
    assert (await _profile(client, host))["cancelCount"] == 0

    host = await _player(client, ntrp=3.0, gender="male")
    partner = await _player(client, ntrp=3.0, gender="male")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-07-02"
    )
    await _agree(client, host, partner, request_id)
    closed = await client.post(
        "/api/v1/match/cancel",
        headers=host,
        json={"requestId": request_id, "reason": "临时有事"},
    )
    assert closed.status_code == 200, closed.text
    assert closed.json()["data"]["cancelCounted"] is True
    assert (await _profile(client, host))["cancelCount"] == 1

    host = await _player(client, ntrp=3.5, gender="male")
    partner = await _player(client, ntrp=3.5, gender="male")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-07-02"
    )
    await _agree(client, host, partner, request_id)
    app.dependency_overrides[get_clock]().moment = datetime(2026, 7, 2, 6, 0, 0)
    late = await client.post(
        "/api/v1/match/cancel",
        headers=partner,
        json={"requestId": request_id},
    )
    assert late.status_code == 200, late.text
    assert late.json()["data"]["request"]["status"] == "cancelled"
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=partner)
    assert detail.json()["data"]["cancelReason"] == 3
    assert late.json()["data"]["cancelCounted"] is True
    assert (await _profile(client, partner))["cancelCount"] == 1
    assert (await _profile(client, host))["cancelCount"] == 0


async def test_arrive_rate_and_credit(client, app) -> None:
    clock = _use_clock(app, datetime(2026, 7, 1, 2, 0, 0))
    court_id = await _court()
    host = await _player(client, ntrp=4.0, gender="male", nickname="主")
    guest = await _player(client, ntrp=4.0, gender="male", nickname="客")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-07-02"
    )
    await _agree(client, host, guest, request_id)
    early = await client.post("/api/v1/match/arrive", headers=host, json={"requestId": request_id})
    assert early.status_code == 403
    assert early.json()["code"] == 40302

    clock.moment = datetime(2026, 7, 2, 6, 0, 0)
    first = await client.post("/api/v1/match/arrive", headers=host, json={"requestId": request_id})
    assert first.status_code == 200, first.text
    assert first.json()["data"]["allArrived"] is False
    assert first.json()["data"]["request"]["status"] == "matched"
    again = await client.post("/api/v1/match/arrive", headers=host, json={"requestId": request_id})
    assert again.status_code == 200
    assert again.json()["data"]["arrived"] is True

    second = await client.post(
        "/api/v1/match/arrive", headers=guest, json={"requestId": request_id}
    )
    assert second.status_code == 200, second.text
    assert second.json()["data"]["allArrived"] is True
    assert second.json()["data"]["request"]["status"] == "completed"

    bad = await client.post(
        "/api/v1/match/rate",
        headers=host,
        json={"requestId": request_id, "ratings": [{"rateeId": "1", "score": 5}]},
    )
    assert bad.status_code == 400
    rated = await client.post(
        "/api/v1/match/rate",
        headers=host,
        json={
            "requestId": request_id,
            "ratings": [{"rateeId": (await _profile(client, guest))["id"], "score": 5}],
        },
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["data"]["creditDelta"] == 1
    assert rated.json()["data"]["myCreditScore"] == 1
    guest_profile = await _profile(client, guest)
    assert guest_profile["avgRating"] == 5
    assert guest_profile["confirmCount"] == 0
    duplicate = await client.post(
        "/api/v1/match/rate",
        headers=host,
        json={"requestId": request_id, "ratings": [{"rateeId": guest_profile["id"], "score": 4}]},
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == 40905

    host_id = (await _profile(client, host))["id"]
    guest_rate = await client.post(
        "/api/v1/match/rate",
        headers=guest,
        json={"requestId": request_id, "ratings": [{"rateeId": host_id, "score": 4}]},
    )
    assert guest_rate.status_code == 200, guest_rate.text
    assert (await _profile(client, host))["avgRating"] == 4

    mine = await client.get("/api/v1/match/my", headers=host, params={"tab": "completed"})
    assert mine.status_code == 200
    assert any(
        row["id"] == request_id and "rate" not in row["availableActions"]
        for row in mine.json()["data"]["list"]
    )


async def test_credit_does_not_go_negative(client, app) -> None:
    clock = _use_clock(app, datetime(2026, 7, 1, 2, 0, 0))
    court_id = await _court()
    host = await _player(client, ntrp=3.5, gender="female")
    guest = await _player(client, ntrp=3.5, gender="female")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-07-02"
    )
    await _agree(client, host, guest, request_id)
    clock.moment = datetime(2026, 7, 2, 6, 0, 0)
    assert (
        await client.post("/api/v1/match/arrive", headers=host, json={"requestId": request_id})
    ).status_code == 200
    assert (
        await client.post("/api/v1/match/arrive", headers=guest, json={"requestId": request_id})
    ).status_code == 200
    host_id = (await _profile(client, host))["id"]
    factory = get_sessionmaker()
    async with factory() as session:
        await session.execute(
            text("UPDATE app_user SET cancel_count = 5 WHERE id = :id"),
            {"id": int(host_id)},
        )
        await session.commit()
    rated = await client.post(
        "/api/v1/match/rate",
        headers=host,
        json={
            "requestId": request_id,
            "ratings": [{"rateeId": (await _profile(client, guest))["id"], "score": 3}],
        },
    )
    assert rated.status_code == 200, rated.text
    assert rated.json()["data"]["myCreditScore"] == 0
    assert rated.json()["data"]["creditDelta"] == 0


async def test_scheduler_expires_and_auto_cancels(client, app) -> None:
    clock = _use_clock(app, datetime(2026, 8, 1, 2, 0, 0))
    court_id = await _court()
    host = await _player(client, ntrp=3.5, gender="male")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-08-02"
    )
    clock.moment = datetime(2026, 8, 2, 6, 0, 0)
    assert await expire_unfilled(clock) >= 1
    assert await expire_unfilled(clock) == 0
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "cancelled"
    assert detail.json()["data"]["cancelReason"] == 4
    assert (await _profile(client, host))["cancelCount"] == 0

    clock.moment = datetime(2026, 8, 1, 2, 0, 0)
    host = await _player(client, ntrp=3.5, gender="male")
    guest = await _player(client, ntrp=3.5, gender="male")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-08-02"
    )
    await _agree(client, host, guest, request_id)
    clock.moment = datetime(2026, 8, 2, 6, 0, 0)
    assert (
        await client.post("/api/v1/match/arrive", headers=host, json={"requestId": request_id})
    ).status_code == 200
    clock.moment = datetime(2026, 8, 2, 6, 0, 0) + timedelta(hours=24)
    assert await auto_cancel_unconfirmed(clock) >= 1
    assert await auto_cancel_unconfirmed(clock) == 0
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "cancelled"
    assert detail.json()["data"]["cancelReason"] == 5
    assert (await _profile(client, host))["cancelCount"] == 0
    assert (await _profile(client, guest))["confirmCount"] == 0

    clock.moment = datetime(2026, 8, 1, 2, 0, 0)
    host = await _player(client, ntrp=3.0, gender="female")
    caught = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-08-02"
    )
    clock.moment = datetime(2026, 8, 2, 6, 0, 0)
    assert await startup_catchup(clock) is True
    detail = await client.get(f"/api/v1/match/detail/{caught}", headers=host)
    assert detail.json()["data"]["status"] == "cancelled"


async def test_doubles_partial_arrival_auto_cancels_without_credit(client, app) -> None:
    clock = _use_clock(app, datetime(2026, 9, 1, 2, 0, 0))
    court_id = await _court()
    host = await _player(client, ntrp=3.5, gender="male")
    partners = [await _player(client, ntrp=3.5, gender="male") for _ in range(3)]
    request_id = await _match(client, app, host, court_id, slotsNeeded=3, date="2026-09-02")
    for partner in partners:
        await _agree(client, host, partner, request_id)
    clock.moment = datetime(2026, 9, 2, 6, 0, 0)
    for headers in (host, *partners[:2]):
        arrived = await client.post(
            "/api/v1/match/arrive", headers=headers, json={"requestId": request_id}
        )
        assert arrived.status_code == 200, arrived.text
        assert arrived.json()["data"]["allArrived"] is False
    clock.moment = datetime(2026, 9, 3, 6, 0, 0)
    assert await auto_cancel_unconfirmed(clock) >= 1
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "cancelled"
    for headers in (host, *partners):
        profile = await _profile(client, headers)
        assert profile["confirmCount"] == 0
        assert profile["cancelCount"] == 0


async def test_concurrent_last_arrivals_complete_once(client, app) -> None:
    clock = _use_clock(app, datetime(2026, 10, 1, 2, 0, 0))
    court_id = await _court()
    host = await _player(client, ntrp=3.5, gender="male")
    guest = await _player(client, ntrp=3.5, gender="male")
    request_id = await _match(
        client, app, host, court_id, matchType="singles", slotsNeeded=1, date="2026-10-02"
    )
    await _agree(client, host, guest, request_id)
    clock.moment = datetime(2026, 10, 2, 6, 0, 0)

    async def arrive(headers: dict[str, str]) -> int:
        response = await client.post(
            "/api/v1/match/arrive", headers=headers, json={"requestId": request_id}
        )
        return response.status_code

    statuses = await asyncio.gather(arrive(host), arrive(guest))
    assert statuses == [200, 200]
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "completed"
    factory = get_sessionmaker()
    async with factory() as session:
        count = await session.scalar(
            text(
                "SELECT COUNT(*) FROM state_transition_log "
                "WHERE request_id = :id AND action = 'arrive' AND to_status = 3"
            ),
            {"id": int(request_id)},
        )
    assert int(count or 0) == 1


async def test_custom_start_expires_and_auto_cancels_on_that_instant(client, app) -> None:
    clock = _use_clock(app, datetime(2026, 8, 1, 2, 0, 0))
    court_id = await _court()
    host = await _player(client, ntrp=3.5, gender="male")
    guest = await _player(client, ntrp=3.5, gender="male")
    request_id = await _match(
        client,
        app,
        host,
        court_id,
        matchType="singles",
        slotsNeeded=1,
        date="2026-08-02",
        startTime="15:20",
        endTime="16:50",
    )
    # 15:20 Shanghai is 07:20 UTC. One minute earlier must leave the request open.
    clock.moment = datetime(2026, 8, 2, 7, 19, 0)
    await expire_unfilled(clock)
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "pending"
    clock.moment = datetime(2026, 8, 2, 7, 20, 0)
    assert await expire_unfilled(clock) >= 1
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "cancelled"
    assert detail.json()["data"]["cancelReason"] == 4

    clock.moment = datetime(2026, 8, 1, 2, 0, 0)
    request_id = await _match(
        client,
        app,
        host,
        court_id,
        matchType="singles",
        slotsNeeded=1,
        date="2026-08-03",
        startTime="15:20",
        endTime="16:50",
    )
    await _agree(client, host, guest, request_id)
    start = datetime(2026, 8, 3, 7, 20, 0)
    clock.moment = start
    assert (
        await client.post("/api/v1/match/arrive", headers=host, json={"requestId": request_id})
    ).status_code == 200
    clock.moment = start + timedelta(hours=23, minutes=59)
    await auto_cancel_unconfirmed(clock)
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "matched"
    clock.moment = start + timedelta(hours=24)
    assert await auto_cancel_unconfirmed(clock) >= 1
    detail = await client.get(f"/api/v1/match/detail/{request_id}", headers=host)
    assert detail.json()["data"]["status"] == "cancelled"
    assert detail.json()["data"]["cancelReason"] == 5


async def test_scheduler_lock_is_exclusive() -> None:
    async def hold() -> None:
        await asyncio.sleep(0.2)

    results = await asyncio.gather(
        run_exclusive("tennis:m3-lock", hold),
        run_exclusive("tennis:m3-lock", hold),
    )
    assert sorted(results) == [False, True]
    assert await run_exclusive("tennis:m3-lock", hold) is True

    conn = await connect_mysql()
    async with conn.cursor() as cursor:
        await cursor.execute("SELECT GET_LOCK(%s, 0)", ("tennis:m3-drop",))
        assert (await cursor.fetchone())[0] == 1
    await conn.ensure_closed()
    follow = await connect_mysql()
    try:
        async with follow.cursor() as cursor:
            await cursor.execute("SELECT GET_LOCK(%s, 0)", ("tennis:m3-drop",))
            assert (await cursor.fetchone())[0] == 1
            await cursor.execute("SELECT RELEASE_LOCK(%s)", ("tennis:m3-drop",))
    finally:
        await follow.ensure_closed()
