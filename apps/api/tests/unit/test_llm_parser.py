from datetime import date
from decimal import Decimal

import pytest

from tennis_match_api.models import AppUser, MatchRequest
from tennis_match_api.services.llm.parser import parse_scores
from tennis_match_api.services.llm.prompt import input_hash, recommend_prompt
from tennis_match_api.services.ranking import final_score, rerank_top


def test_parse_scores_accepts_fences_strings_and_clamps() -> None:
    raw = """```json
    {"results":[{"id":"r1","score":"88","reason":"风格接近\\n适合双打"},{"id":"r9","score":10,"reason":"忽略"}]}
    ```"""
    scores, outcome = parse_scores(raw, ["r1", "r2"])
    assert outcome == "ok"
    assert scores["r1"].score == 88
    assert scores["r1"].store is True
    assert scores["r1"].reason == "风格接近 适合双打"
    assert scores["r2"].score == 50
    assert scores["r2"].store is False
    assert "r9" not in scores

    clamped, outcome = parse_scores('{"results":[{"id":"r1","score":140,"reason":"x"}]}', ["r1"])
    assert outcome == "ok"
    assert clamped["r1"].score == 100
    assert clamped["r1"].store is True

    missing, outcome = parse_scores('{"score": true, "reason": "nope"}', ["r1"])
    assert outcome == "ok"
    assert missing["r1"].store is False

    bad, outcome = parse_scores("not json", ["r1", "r2"])
    assert outcome == "bad_output"
    assert bad["r1"].score == 50 and bad["r2"].store is False

    long_reason, _ = parse_scores(
        '{"results":[{"id":"r1","score":70,"reason":"' + ("字" * 40) + '"}]}',
        ["r1"],
    )
    assert long_reason["r1"].reason is not None
    assert len(long_reason["r1"].reason) == 30


def test_input_hash_tracks_profile_prompt_and_model() -> None:
    publisher = AppUser(ntrp=Decimal("3.5"), style_mask=2, bio="周末", age=30, gender=1)
    candidate = AppUser(ntrp=Decimal("4.0"), style_mask=4, bio="想练球", age=28, gender=2)
    request = MatchRequest(
        match_type=2,
        gender_pref=0,
        expected_ntrp_min=Decimal("3.0"),
        expected_ntrp_max=Decimal("4.0"),
    )
    base = input_hash(publisher, candidate, request, prompt_version="v1", model_name="m")
    publisher.bio = "改了简介"
    changed_bio = input_hash(publisher, candidate, request, prompt_version="v1", model_name="m")
    changed_model = input_hash(
        publisher, candidate, request, prompt_version="v1", model_name="other"
    )
    changed_prompt = input_hash(
        publisher, candidate, request, prompt_version="v2", model_name="other"
    )
    assert len({base, changed_bio, changed_model, changed_prompt}) == 4
    request.time_slot = "23:00-01:00"
    request.match_date = date(2026, 6, 4)
    changed_time = input_hash(publisher, candidate, request, prompt_version="v1", model_name="m")
    assert changed_time not in {base, changed_bio, changed_model, changed_prompt}
    prompt = recommend_prompt(candidate, [("r1", publisher, request)])
    assert "时间：2026-06-04 23:00-次日01:00" in prompt


def test_final_score_weights_and_stable_rerank() -> None:
    score = final_score(1, 1, 100, weight_credit=0.3, weight_ntrp=0.3, weight_llm=0.4)
    assert score == pytest.approx(1)
    assert final_score(0, 1, None, weight_credit=0.3, weight_ntrp=0.3, weight_llm=0.4) is None
    rows = [("early", 1), ("late", 2), ("tail", 3)]
    ordered = rerank_top(
        rows,
        {1: 0.2, 2: 0.9},
        top_n=2,
        row_id=lambda row: row[1],
        row_start=lambda row: row[0],
    )
    assert [row[1] for row in ordered] == [2, 1, 3]
    tied = rerank_top(
        [("b", 2), ("a", 1)],
        {1: 0.5, 2: 0.5},
        top_n=2,
        row_id=lambda row: row[1],
        row_start=lambda row: row[0],
    )
    assert [row[1] for row in tied] == [1, 2]
