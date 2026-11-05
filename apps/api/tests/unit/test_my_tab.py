from tennis_match_api.services.lifecycle_service import classify_tab, matches_type


def test_tabs_follow_the_my_matches_table() -> None:
    assert (
        classify_tab(status=1, role="publisher", application_status=None, left=False) == "pending"
    )
    assert (
        classify_tab(status=1, role="applicant", application_status="pending", left=False)
        == "pending"
    )
    assert (
        classify_tab(status=1, role="partner", application_status="agreed", left=False) == "pending"
    )
    assert (
        classify_tab(status=2, role="partner", application_status="agreed", left=False)
        == "confirmed"
    )
    assert (
        classify_tab(status=3, role="publisher", application_status=None, left=False) == "completed"
    )
    assert (
        classify_tab(status=4, role="publisher", application_status=None, left=False) == "cancelled"
    )
    assert (
        classify_tab(status=1, role="applicant", application_status="rejected", left=False)
        == "cancelled"
    )
    assert (
        classify_tab(status=1, role="applicant", application_status="cancelled", left=True)
        == "cancelled"
    )


def test_type_filters() -> None:
    assert matches_type(
        "published",
        is_publisher=True,
        has_application=False,
        is_participant=True,
        reached_matched=True,
    )
    assert not matches_type(
        "applied",
        is_publisher=True,
        has_application=False,
        is_participant=True,
        reached_matched=True,
    )
    assert matches_type(
        "matched",
        is_publisher=True,
        has_application=False,
        is_participant=True,
        reached_matched=True,
    )
    assert not matches_type(
        "matched",
        is_publisher=False,
        has_application=True,
        is_participant=True,
        reached_matched=False,
    )
