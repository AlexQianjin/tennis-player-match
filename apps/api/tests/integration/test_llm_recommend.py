import asyncio
import json
import logging
import re
import time
from datetime import datetime

import pytest
from httpx import ASGITransport, AsyncClient
from tests.integration.test_match_http import _court, _player, _publish, _use_clock

from tennis_match_api.config import get_settings
from tennis_match_api.main import create_app
from tennis_match_api.services.llm.client import get_llm_client


class FakeLLM:
    def __init__(self, mode: str = "ok", delay: float = 0) -> None:
        self.mode = mode
        self.delay = delay
        self.calls = 0

    async def complete(self, *, system: str, user: str) -> str:
        del system
        self.calls += 1
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.mode == "throw":
            raise RuntimeError("model down")
        if self.mode == "bad":
            return "not-json"
        if self.mode == "missing":
            return '{"results":[{"id":"r1","reason":"只有理由"}]}'
        ids = re.findall(r"id=(r\d+)", user)
        results = []
        for index, short in enumerate(ids):
            score = 95 if len(ids) > 1 and index == len(ids) - 1 else 80
            results.append({"id": short, "score": score, "reason": "风格接近适合双打"})
        return json.dumps({"results": results}, ensure_ascii=False)


@pytest.fixture
def llm_app(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("LLM_ENABLED", "true")
    monkeypatch.setenv("AI_MODEL_BASE_URL", "http://127.0.0.1:9/v1")
    monkeypatch.setenv("AI_MODEL_API_KEY", "test-key")
    monkeypatch.setenv("AI_MODEL_NAME", "fake-model")
    monkeypatch.setenv("LLM_DAILY_LIMIT_GLOBAL", "20")
    monkeypatch.setenv("LLM_DAILY_LIMIT_PER_USER", "10")
    get_settings.cache_clear()
    application = create_app()
    yield application
    get_settings.cache_clear()


def _install(app, fake: FakeLLM, moment: datetime) -> None:
    _use_clock(app, moment)
    app.dependency_overrides[get_llm_client] = lambda: fake


async def _recommend(client: AsyncClient, headers: dict[str, str], court_id: str, **params: object):
    response = await client.get(
        "/api/v1/match/recommend",
        headers=headers,
        params={"city": "武汉", "courtId": court_id, **params},
    )
    assert response.status_code == 200, response.text
    return response.json()["data"]


async def test_llm_reranks_and_shows_reason_on_applications(llm_app) -> None:
    fake = FakeLLM()
    _install(llm_app, fake, datetime(2026, 6, 1, 2, 0, 0))
    transport = ASGITransport(app=llm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        early = await _player(client, ntrp=4.0, gender="male", nickname="早")
        late = await _player(client, ntrp=4.0, gender="male", nickname="晚")
        viewer = await _player(client, ntrp=4.0, gender="male", nickname="看")
        court_id = await _court()
        first = await client.post(
            "/api/v1/match/publish",
            headers=early,
            json=_publish(court_id, date="2026-06-02"),
        )
        second = await client.post(
            "/api/v1/match/publish",
            headers=late,
            json=_publish(court_id, date="2026-06-04"),
        )
        assert first.status_code == 200 and second.status_code == 200
        early_id = first.json()["data"]["id"]
        late_id = second.json()["data"]["id"]

        page = await _recommend(client, viewer, court_id)
        assert page["llmApplied"] is True
        assert fake.calls == 1
        ids = [item["id"] for item in page["list"]]
        assert ids.index(late_id) < ids.index(early_id)
        late_item = next(item for item in page["list"] if item["id"] == late_id)
        assert late_item["llmScore"] == 95
        assert late_item["matchReason"] == "风格接近适合双打"
        assert late_item["finalScore"] is not None

        again = await _recommend(client, viewer, court_id)
        assert again["llmApplied"] is True
        assert fake.calls == 1

        applied = await client.post(
            "/api/v1/match/apply",
            headers=viewer,
            json={"requestId": late_id},
        )
        assert applied.status_code == 200, applied.text
        listed = await client.get(
            "/api/v1/match/applications",
            headers=late,
            params={"requestId": late_id},
        )
        assert listed.status_code == 200, listed.text
        row = listed.json()["data"]["list"][0]
        assert row["matchReason"] == "风格接近适合双打"
        assert row["llmScore"] == 95


async def test_slow_model_returns_rules_then_background_cache(llm_app, caplog) -> None:
    fake = FakeLLM(delay=4)
    _install(llm_app, fake, datetime(2026, 6, 1, 2, 0, 0))
    transport = ASGITransport(app=llm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        publisher = await _player(client, ntrp=4.0, gender="male")
        viewer = await _player(client, ntrp=4.0, gender="male")
        court_id = await _court()
        created = await client.post(
            "/api/v1/match/publish",
            headers=publisher,
            json=_publish(court_id),
        )
        assert created.status_code == 200, created.text
        request_id = created.json()["data"]["id"]
        with caplog.at_level(logging.INFO, logger="tennis_match_api.services.llm.scoring"):
            started = time.perf_counter()
            page = await _recommend(client, viewer, court_id)
            elapsed = time.perf_counter() - started
        assert elapsed < 3.5
        assert page["llmApplied"] is False
        item = next(row for row in page["list"] if row["id"] == request_id)
        assert item["llmScore"] is None
        assert item["ruleScore"] >= 0
        assert any(getattr(record, "outcome", None) == "timeout" for record in caplog.records)
        await asyncio.sleep(2)
        cached = await _recommend(client, viewer, court_id)
        assert fake.calls == 1
        assert cached["llmApplied"] is True
        hit = next(row for row in cached["list"] if row["id"] == request_id)
        assert hit["matchReason"] == "风格接近适合双打"
        assert hit["llmScore"] == 80


async def test_bad_json_missing_fields_and_errors_do_not_stick(llm_app) -> None:
    transport = ASGITransport(app=llm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        for mode in ("bad", "missing", "throw"):
            fake = FakeLLM(mode=mode)
            _install(llm_app, fake, datetime(2026, 6, 1, 2, 0, 0))
            publisher = await _player(client, ntrp=3.5, gender="male")
            viewer = await _player(client, ntrp=3.5, gender="male")
            court_id = await _court()
            created = await client.post(
                "/api/v1/match/publish",
                headers=publisher,
                json=_publish(court_id),
            )
            assert created.status_code == 200, created.text
            request_id = created.json()["data"]["id"]
            first = await _recommend(client, viewer, court_id)
            second = await _recommend(client, viewer, court_id)
            item = next(row for row in first["list"] if row["id"] == request_id)
            if mode == "missing":
                assert first["llmApplied"] is True
                assert item["llmScore"] == 50
                assert item["matchReason"] is None
                assert fake.calls == 2
            else:
                assert first["llmApplied"] is False
                assert item["llmScore"] is None
                assert second["llmApplied"] is False
                assert fake.calls == 2


async def test_daily_limit_resets_on_shanghai_day(monkeypatch, llm_app) -> None:
    monkeypatch.setenv("LLM_DAILY_LIMIT_PER_USER", "1")
    get_settings.cache_clear()
    fake = FakeLLM()
    clock = _use_clock(llm_app, datetime(2026, 6, 1, 2, 0, 0))
    llm_app.dependency_overrides[get_llm_client] = lambda: fake
    transport = ASGITransport(app=llm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        viewer = await _player(client, ntrp=4.0, gender="male")
        court_id = await _court()
        first_publisher = await _player(client, ntrp=4.0, gender="male")
        second_publisher = await _player(client, ntrp=4.0, gender="male")
        created = await client.post(
            "/api/v1/match/publish",
            headers=first_publisher,
            json=_publish(court_id, date="2026-06-02"),
        )
        assert created.status_code == 200, created.text
        first = await _recommend(client, viewer, court_id)
        assert first["llmApplied"] is True
        assert fake.calls == 1
        created = await client.post(
            "/api/v1/match/publish",
            headers=second_publisher,
            json=_publish(court_id, date="2026-06-03"),
        )
        assert created.status_code == 200, created.text
        blocked = await _recommend(client, viewer, court_id)
        assert blocked["llmApplied"] is False
        assert fake.calls == 1
        clock.moment = datetime(2026, 6, 2, 2, 0, 0)
        again = await _recommend(client, viewer, court_id)
        assert again["llmApplied"] is True
        assert fake.calls == 2


async def test_page_three_does_not_call_the_model(llm_app) -> None:
    fake = FakeLLM()
    _install(llm_app, fake, datetime(2026, 6, 1, 2, 0, 0))
    transport = ASGITransport(app=llm_app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        publisher = await _player(client, ntrp=4.0, gender="male")
        viewer = await _player(client, ntrp=4.0, gender="male")
        court_id = await _court()
        created = await client.post(
            "/api/v1/match/publish",
            headers=publisher,
            json=_publish(court_id),
        )
        assert created.status_code == 200
        page = await _recommend(client, viewer, court_id, page=3)
        assert page["llmApplied"] is False
        assert fake.calls == 0


async def test_debug_routes_stay_unregistered(client) -> None:
    response = await client.post(
        "/api/v1/llm/match/score",
        json={"publisherId": "1", "candidateId": "2"},
    )
    assert response.status_code == 404
