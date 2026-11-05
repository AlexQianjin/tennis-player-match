from decimal import Decimal

from tennis_match_api.services.ranking import credit_norm, ntrp_closeness, rule_score


def test_credit_norm_boundaries() -> None:
    assert credit_norm(0) == 0
    assert credit_norm(-3) == 0
    assert 0.2 < credit_norm(1) < 0.25
    assert credit_norm(20) == 1
    assert credit_norm(100) == 1
    assert credit_norm(5, cap=0) == 0


def test_ntrp_closeness_clamps() -> None:
    assert ntrp_closeness(Decimal("3.5"), Decimal("3.5")) == 1
    assert ntrp_closeness(Decimal("3.5"), Decimal("4.0")) == 0
    assert ntrp_closeness(Decimal("3.5"), Decimal("4.5")) == 0
    assert ntrp_closeness(Decimal("3.0"), Decimal("3.5"), hard_diff=Decimal("0")) == 0


def test_rule_score_renormalizes_the_two_rule_weights() -> None:
    score = rule_score(1, 0, weight_credit=0.3, weight_ntrp=0.3)
    assert score == 0.5
    assert rule_score(1, 1, weight_credit=0, weight_ntrp=0) == 0
