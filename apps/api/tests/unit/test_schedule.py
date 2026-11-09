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


def test_overnight_end_is_the_next_shanghai_day() -> None:
    start_at, end_at, slot = validate_booking(
        shanghai_date(_now()).replace(day=4), "23:00", "01:00", _now()
    )
    assert slot == "23:00-01:00"
    assert start_at == datetime(2026, 6, 4, 15, 0, 0)
    assert end_at == datetime(2026, 6, 4, 17, 0, 0)
    assert end_at - start_at == timedelta(hours=2)


def test_bounds_and_window() -> None:
    today = shanghai_date(_now())
    with pytest.raises(ScheduleRejected, match="过去"):
        validate_booking(today, "09:00", "11:00", _now())
    with pytest.raises(ScheduleRejected, match="过去"):
        validate_booking(today.replace(day=1), "13:00", "15:00", _now())
    with pytest.raises(ScheduleRejected, match="30 分钟"):
        validate_booking(today.replace(day=3), "15:20", "15:40", _now())
    with pytest.raises(ScheduleRejected, match="晚于开始"):
        validate_booking(today.replace(day=3), "15:20", "15:20", _now())
    with pytest.raises(ScheduleRejected, match="8 小时"):
        validate_booking(today.replace(day=3), "10:00", "19:00", _now())
    with pytest.raises(ScheduleRejected, match="8 小时"):
        validate_booking(today.replace(day=3), "18:00", "09:00", _now())
    with pytest.raises(ScheduleRejected, match="30 天"):
        validate_booking(today + timedelta(days=DATE_WINDOW_DAYS + 1), "10:00", "12:00", _now())
    with pytest.raises(ScheduleRejected, match="格式"):
        validate_booking(today.replace(day=3), "25:00", "26:00", _now())

    start_at, end_at, slot = validate_booking(today.replace(day=3), "15:20", "15:50", _now())
    assert slot == "15:20-15:50"
    assert end_at - start_at == timedelta(minutes=30)
    start_at, end_at, _slot = validate_booking(today.replace(day=3), "10:00", "18:00", _now())
    assert end_at - start_at == timedelta(hours=8)
    last = today + timedelta(days=DATE_WINDOW_DAYS)
    validate_booking(last, "23:00", "01:00", _now())


def test_exact_now_is_not_in_the_future() -> None:
    # 14:00 Shanghai == 06:00 UTC.
    now = datetime(2026, 6, 1, 6, 0, 0)
    with pytest.raises(ScheduleRejected, match="过去"):
        validate_booking(shanghai_date(now), "14:00", "16:00", now)
    _start, _end, slot = validate_booking(shanghai_date(now), "15:00", "17:00", now)
    assert slot == "15:00-17:00"


def test_filter_offsets_cover_overnight_windows() -> None:
    assert filter_offsets("15:00-16:00") == (15 * 60 - 8 * 60, 16 * 60 - 8 * 60)
    start, end = filter_offsets("23:00-01:00")
    assert end - start == 120
    assert start == 23 * 60 - 8 * 60
    morning_start, morning_end = filter_offsets("00:30-02:00")
    assert morning_end - morning_start == 90
    assert morning_start == 30 - 8 * 60
    with pytest.raises(ScheduleRejected):
        filter_offsets("nope")
    with pytest.raises(ScheduleRejected):
        filter_offsets("14:00-14:00")
