from datetime import datetime, timedelta

import pytest

from tennis_match_api.schedule import (
    DATE_WINDOW_DAYS,
    ScheduleRejected,
    filter_offsets,
    shanghai_date,
    validate_booking,
)


def _now() -> datetime:
    # 2026-06-01 13:06 Asia/Shanghai.
    return datetime(2026, 6, 1, 5, 6, 0)


def test_same_day_window_is_utc_shanghai() -> None:
    start_at, end_at, slot = validate_booking(
        shanghai_date(_now()).replace(day=3), "15:20", "16:50", _now()
    )
    assert slot == "15:20-16:50"
    assert start_at == datetime(2026, 6, 3, 7, 20, 0)
    assert end_at == datetime(2026, 6, 3, 8, 50, 0)


def test_playable_hours_are_same_day_07_to_22() -> None:
    day = shanghai_date(_now()).replace(day=3)
    with pytest.raises(ScheduleRejected, match="07:00"):
        validate_booking(day, "06:30", "08:30", _now())
    with pytest.raises(ScheduleRejected, match="22:00"):
        validate_booking(day, "20:00", "22:30", _now())
    with pytest.raises(ScheduleRejected, match="晚于开始"):
        validate_booking(day, "21:00", "01:00", _now())
    with pytest.raises(ScheduleRejected, match="晚于开始"):
        validate_booking(day, "18:00", "09:00", _now())
    with pytest.raises(ScheduleRejected, match="30 分钟"):
        validate_booking(day, "21:40", "22:00", _now())

    _start, end_at, slot = validate_booking(day, "07:00", "09:00", _now())
    assert slot == "07:00-09:00"
    assert end_at == datetime(2026, 6, 3, 1, 0, 0)
    _start, end_at, slot = validate_booking(day, "21:30", "22:00", _now())
    assert slot == "21:30-22:00"
    assert end_at == datetime(2026, 6, 3, 14, 0, 0)
    start_at, end_at, _slot = validate_booking(day, "07:00", "15:00", _now())
    assert end_at - start_at == timedelta(hours=8)


def test_bounds_and_window() -> None:
    today = shanghai_date(_now())
    with pytest.raises(ScheduleRejected, match="过去"):
        validate_booking(today, "09:00", "11:00", _now())
    with pytest.raises(ScheduleRejected, match="过去"):
        validate_booking(today, "13:00", "15:00", _now())
    with pytest.raises(ScheduleRejected, match="30 分钟"):
        validate_booking(today.replace(day=3), "15:20", "15:40", _now())
    with pytest.raises(ScheduleRejected, match="晚于开始"):
        validate_booking(today.replace(day=3), "15:20", "15:20", _now())
    with pytest.raises(ScheduleRejected, match="8 小时"):
        validate_booking(today.replace(day=3), "10:00", "19:00", _now())
    with pytest.raises(ScheduleRejected, match="30 天"):
        validate_booking(today + timedelta(days=DATE_WINDOW_DAYS + 1), "10:00", "12:00", _now())
    with pytest.raises(ScheduleRejected, match="格式"):
        validate_booking(today.replace(day=3), "25:00", "26:00", _now())

    start_at, end_at, slot = validate_booking(today.replace(day=3), "15:20", "15:50", _now())
    assert slot == "15:20-15:50"
    assert end_at - start_at == timedelta(minutes=30)
    last = today + timedelta(days=DATE_WINDOW_DAYS)
    validate_booking(last, "21:00", "22:00", _now())


def test_exact_now_is_not_in_the_future() -> None:
    # 14:00 Shanghai == 06:00 UTC.
    now = datetime(2026, 6, 1, 6, 0, 0)
    with pytest.raises(ScheduleRejected, match="过去"):
        validate_booking(shanghai_date(now), "14:00", "16:00", now)
    _start, _end, slot = validate_booking(shanghai_date(now), "15:00", "17:00", now)
    assert slot == "15:00-17:00"


def test_filter_offsets_stay_on_one_day() -> None:
    assert filter_offsets("15:00-16:00") == (15 * 60 - 8 * 60, 16 * 60 - 8 * 60)
    assert filter_offsets("21:30-22:00") == (21 * 60 + 30 - 8 * 60, 22 * 60 - 8 * 60)
    with pytest.raises(ScheduleRejected, match="晚于开始"):
        filter_offsets("23:00-01:00")
    with pytest.raises(ScheduleRejected):
        filter_offsets("nope")
    with pytest.raises(ScheduleRejected):
        filter_offsets("14:00-14:00")
