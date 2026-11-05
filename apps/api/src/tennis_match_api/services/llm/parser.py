"""Parse model JSON into clamped scores. Invalid items become 50 and are not stored."""

import json
import re
from dataclasses import dataclass

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


@dataclass(frozen=True)
class ScoreItem:
    score: int
    reason: str | None
    store: bool


def parse_scores(raw: str, expected_ids: list[str]) -> tuple[dict[str, ScoreItem], str]:
    """Return scores for every expected id and an outcome of ok or bad_output."""
    try:
        payload = _load_json(raw)
    except (ValueError, json.JSONDecodeError):
        return {item_id: ScoreItem(50, None, False) for item_id in expected_ids}, "bad_output"
    found = _index_results(payload)
    scores: dict[str, ScoreItem] = {}
    for item_id in expected_ids:
        parsed = found.get(item_id)
        if parsed is None:
            scores[item_id] = ScoreItem(50, None, False)
            continue
        score, reason, store = parsed
        scores[item_id] = ScoreItem(score, reason, store)
    return scores, "ok"


def _load_json(raw: str) -> object:
    text = raw.strip()
    if text.startswith("```"):
        text = _FENCE.sub("", text).strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("no json object")
    return json.loads(text[start : end + 1])


def _index_results(payload: object) -> dict[str, tuple[int, str | None, bool]]:
    rows: list[object]
    if isinstance(payload, dict) and "results" in payload:
        rows = payload["results"] if isinstance(payload["results"], list) else []
    elif isinstance(payload, dict) and "score" in payload:
        rows = [payload]
    else:
        rows = []
    found: dict[str, tuple[int, str | None, bool]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        item_id = row.get("id")
        if not isinstance(item_id, str) or not item_id:
            continue
        score, store = _score(row.get("score"))
        reason = _reason(row.get("reason")) if store else None
        found[item_id] = (score, reason, store)
    return found


def _score(value: object) -> tuple[int, bool]:
    if isinstance(value, bool) or value is None:
        return 50, False
    if isinstance(value, str):
        text = value.strip()
        if not text or not _is_int(text):
            return 50, False
        value = int(text)
    if isinstance(value, float) and not value.is_integer():
        return 50, False
    if not isinstance(value, int):
        return 50, False
    if value < 0 or value > 100:
        return max(0, min(100, value)), True
    return value, True


def _is_int(text: str) -> bool:
    return text.isdigit() or (text.startswith("-") and text[1:].isdigit())


def _reason(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    text = " ".join(value.replace("\n", " ").split())
    if not text:
        return None
    return text[:30]
