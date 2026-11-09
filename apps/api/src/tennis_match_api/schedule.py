"""Asia/Shanghai match windows.

A booking is a start date plus two clocks. When the end clock is not after the
start clock, the end falls on the next calendar day (23:00–01:00 is two hours,
not a reversed same-day range). ``match_date`` is always the start date.
``start_at`` / ``end_at`` are the instants schedulers and filters use.

Write rules, enforced again on publish:

- start is strictly after now
- the start date is today through today + 30 days (Asia/Shanghai)
- duration is 30 minutes through 8 hours

Eight hours is long enough for a full session and still rejects an accidental
overnight such as 18:00–09:00 (15 hours). The columns already store arbitrary
instants, so these bounds are application checks rather than a new CHECK that
would reject rows written before the bound existed.
"""

import re
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

SHANGHAI = ZoneInfo("Asia/Shanghai")
MIN_DURATION = timedelta(minutes=30)
MAX_DURATION = timedelta(hours=8)
DATE_WINDOW_DAYS = 30
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
    """Naive UTC bounds. An end clock that is not after the start is the next day."""
    start_local = datetime.combine(match_date, start, tzinfo=SHANGHAI)
    end_local = datetime.combine(match_date, end, tzinfo=SHANGHAI)
    if end_local <= start_local:
        end_local += timedelta(days=1)
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
    if start == end:
        raise ScheduleRejected("结束时间需要晚于开始时间")
    start_at, end_at = resolve_interval(match_date, start, end)
    duration = end_at - start_at
    today = shanghai_date(now)
    if match_date < today or start_at <= as_utc_naive(now):
        raise ScheduleRejected("不能选择过去的时间")
    if match_date > today + timedelta(days=DATE_WINDOW_DAYS):
        raise ScheduleRejected("开始日期需在今天起 30 天内")
    if duration < MIN_DURATION:
        raise ScheduleRejected("时长至少 30 分钟")
    if duration > MAX_DURATION:
        raise ScheduleRejected("时长不能超过 8 小时")
    slot = f"{start.strftime('%H:%M')}-{end.strftime('%H:%M')}"
    return start_at, end_at, slot


def filter_offsets(slot: str) -> tuple[int, int]:
    """Minutes added to UTC midnight of an anchor date for a half-open window.

    Shanghai is UTC+8 with no DST. A negative offset is the previous UTC evening,
    which is that anchor date's morning in Shanghai. When the end clock is not
    after the start clock, the window ends the next day.
    """
    text = slot.strip()
    if text.count("-") != 1:
        raise ScheduleRejected("时段格式不正确")
    start_text, end_text = text.split("-", 1)
    start = parse_clock(start_text)
    end = parse_clock(end_text)
    if start == end:
        raise ScheduleRejected("结束时间需要晚于开始时间")
    start_min = start.hour * 60 + start.minute - int(_UTC_OFFSET.total_seconds() // 60)
    end_min = end.hour * 60 + end.minute - int(_UTC_OFFSET.total_seconds() // 60)
    if end_min <= start_min:
        end_min += 24 * 60
    return start_min, end_min
