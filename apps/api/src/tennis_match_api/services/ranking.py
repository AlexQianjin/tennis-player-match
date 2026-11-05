"""Rule score and the LLM final score from DESIGN §9.2."""

import math
from decimal import Decimal


def credit_norm(credit: int, cap: int = 20) -> float:
    if cap <= 0:
        return 0.0
    return min(1.0, math.log1p(max(credit, 0)) / math.log1p(cap))


def ntrp_closeness(left: Decimal, right: Decimal, hard_diff: Decimal = Decimal("0.5")) -> float:
    if hard_diff <= 0:
        return 1.0 if left == right else 0.0
    distance = abs(left - right) / hard_diff
    return max(0.0, min(1.0, 1 - float(distance)))


def rule_score(
    credit: float,
    closeness: float,
    *,
    weight_credit: float,
    weight_ntrp: float,
) -> float:
    total = weight_credit + weight_ntrp
    if total <= 0:
        return 0.0
    return (weight_credit * credit + weight_ntrp * closeness) / total


def final_score(
    credit: float,
    closeness: float,
    llm: int | None,
    *,
    weight_credit: float,
    weight_ntrp: float,
    weight_llm: float,
) -> float | None:
    """Weighted sum. None when this row has no LLM score."""
    if llm is None:
        return None
    return weight_credit * credit + weight_ntrp * closeness + weight_llm * (llm / 100)


def rerank_top[T](
    rule_order: list[T],
    finals: dict[int, float],
    *,
    top_n: int,
    row_id,
    row_start,
) -> list[T]:
    """Reorder the LLM shortlist by finalScore, then start time, then id."""
    head = list(rule_order[:top_n])
    tail = list(rule_order[top_n:])
    head.sort(key=lambda row: (-finals[row_id(row)], row_start(row), row_id(row)))
    return head + tail
