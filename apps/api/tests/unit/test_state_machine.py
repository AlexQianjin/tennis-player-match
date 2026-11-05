import pytest

from tennis_match_api.services.state_machine import (
    TransitionError,
    available_actions,
    ensure_transition,
)


def test_publish_agree_and_reject_are_legal() -> None:
    ensure_transition("match_request", None, "publish", 1)
    ensure_transition("match_request", 1, "agree", 1)
    ensure_transition("match_request", 1, "agree", 2)
    ensure_transition("application", 1, "reject", 3)
    ensure_transition("application", 1, "withdraw", 4)


def test_illegal_transition_is_rejected() -> None:
    with pytest.raises(TransitionError):
        ensure_transition("match_request", 4, "agree", 2)
    with pytest.raises(TransitionError):
        ensure_transition("match_request", 1, "arrive", 3)
    with pytest.raises(TransitionError):
        ensure_transition("application", 3, "agree", 2)


def test_available_actions_follow_role_status_and_time() -> None:
    assert available_actions(
        status=1,
        role="publisher",
        application_status=None,
        started=False,
        in_arrive_window=False,
        rated=False,
        filled=False,
    ) == ["viewApplications", "cancel"]
    assert available_actions(
        status=1,
        role="none",
        application_status=None,
        started=False,
        in_arrive_window=False,
        rated=False,
        filled=False,
    ) == ["apply"]
    assert (
        available_actions(
            status=1,
            role="none",
            application_status=None,
            started=True,
            in_arrive_window=True,
            rated=False,
            filled=False,
        )
        == []
    )
    assert available_actions(
        status=1,
        role="applicant",
        application_status="pending",
        started=False,
        in_arrive_window=False,
        rated=False,
        filled=False,
    ) == ["withdraw"]
    assert available_actions(
        status=1,
        role="partner",
        application_status="agreed",
        started=False,
        in_arrive_window=False,
        rated=False,
        filled=False,
    ) == ["cancel"]
    assert available_actions(
        status=2,
        role="partner",
        application_status="agreed",
        started=True,
        in_arrive_window=True,
        rated=False,
        filled=True,
    ) == ["cancel", "arrive"]
    assert available_actions(
        status=2,
        role="publisher",
        application_status=None,
        started=False,
        in_arrive_window=False,
        rated=False,
        filled=True,
    ) == ["cancel"]
    assert available_actions(
        status=3,
        role="partner",
        application_status="agreed",
        started=True,
        in_arrive_window=False,
        rated=False,
        filled=True,
    ) == ["rate"]
    assert (
        available_actions(
            status=4,
            role="publisher",
            application_status=None,
            started=True,
            in_arrive_window=False,
            rated=False,
            filled=False,
        )
        == []
    )
