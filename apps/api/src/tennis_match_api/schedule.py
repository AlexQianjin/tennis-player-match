"""Asia/Shanghai match windows.

A booking is one calendar date and two clocks on that date. Playable hours are
07:00–22:00. The end is never the next day. ``start_at`` / ``end_at`` are the
instants schedulers and filters use.

Write rules, enforced on publish only (older rows outside the window still read):

- start is strictly after now
- the start date is today through today + 30 days (Asia/Shanghai)
- start >= 07:00 and end <= 22:00, both on that date, end after start
- duration is 30 minutes through 8 hours

There is no CHECK for these bounds, so a row written before the window still loads.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
MIN_DURATION = timedelta(minutes=30)
MAX_DURATION = timedelta(hours=8)
DATE_WINDOW_DAYS = 30
OPEN_TIME = time(7, 0)
CLOSE_TIME = time(22, 0)
_UTC_OFFSET = timedelta(hours=8)
_CLOCK = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")


class ScheduleRejected(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def shanghai_date(now: datetime) -> date:
    aware = now if now.tzinfo is not None else now.replace(tzinfo=UTC)
    return aware.astimezone(SHANGHAI).date()


def as_utc_naive(now: datetime) -> datetime:
    if now.tzinfo is None:
        return now
    return now.astimezone(UTC).replace(tzinfo=None)


def parse_clock(value: str) -> time:
    matched = _CLOCK.fullmatch(value.strip())
    if matched is None:
        raise ScheduleRejected("时段格式不正确")
    return time(int(matched.group(1)), int(matched.group(2)))


def resolve_interval(match_date: date, start: time, end: time) -> tuple[datetime, datetime]:
    """Naive UTC bounds on the same Shanghai date. End must be after start."""
    if end <= start:
        raise ScheduleRejected("结束时间需要晚于开始时间")
    start_local = datetime.combine(match_date, start, tzinfo=SHANGHAI)
    end_local = datetime.combine(match_date, end, tzinfo=SHANGHAI)
    start_at = start_local.astimezone(UTC).replace(tzinfo=None)
    end_at = end_local.astimezone(UTC).replace(tzinfo=None)
    return start_at, end_at


def validate_booking(
    match_date: date,
    start_text: str,
    end_text: str,
    now: datetime,
) -> tuple[datetime, datetime, str]:
    """Return naive UTC ``(start_at, end_at, time_slot)`` or raise ``ScheduleRejected``."""
    start = parse_clock(start_text)
    end = parse_clock(end_text)
    today = shanghai_date(now)
    start_local = datetime.combine(match_date, start, tzinfo=SHANGHAI)
    start_at = start_local.astimezone(UTC).replace(tzinfo=None)
    if match_date < today or start_at <= as_utc_naive(now):
        raise ScheduleRejected("不能选择过去的时间")
    if match_date > today + timedelta(days=DATE_WINDOW_DAYS):
        raise ScheduleRejected("开始日期需在今天起 30 天内")
    if start < OPEN_TIME:
        raise ScheduleRejected("开始时间不能早于 07:00")
    if end > CLOSE_TIME:
        raise ScheduleRejected("结束时间不能晚于 22:00")
    start_at, end_at = resolve_interval(match_date, start, end)
    duration = end_at - start_at
    if duration < MIN_DURATION:
        raise ScheduleRejected("时长至少 30 分钟")
    if duration > MAX_DURATION:
        raise ScheduleRejected("时长不能超过 8 小时")
    slot = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    return start_at, end_at, slot


def filter_offsets(slot: str) -> tuple[int, int]:
    """Minutes added to UTC midnight of the start date for a half-open same-day window.

    Shanghai is UTC+8 with no DST. Filters may name any same-day clocks so an
    older row outside 07:00–22:00 can still be matched. A window that would
    cross midnight is rejected instead of being extended into the next day.
    """
    text = slot.strip()
    if text.count("-") != 1:
        raise ScheduleRejected("时段格式不正确")
    start_text, end_text = text.split("-", 1)
    start = parse_clock(start_text)
    end = parse_clock(end_text)
    if end <= start:
        raise ScheduleRejected("结束时间需要晚于开始时间")
    offset = int(_UTC_OFFSET.total_seconds() // 60)
    return start.hour * 60 + start.minute - offset, end.hour * 60 + end.minute - offset
