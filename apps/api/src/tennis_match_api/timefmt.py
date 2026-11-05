import calendar
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

_SHANGHAI = ZoneInfo("Asia/Shanghai")


def add_months(moment: datetime, months: int) -> datetime:
    """Add calendar months to a naive UTC timestamp (MySQL INTERVAL n MONTH)."""
    month_index = moment.month - 1 + months
    year = moment.year + month_index // 12
    month = month_index % 12 + 1
    day = min(moment.day, calendar.monthrange(year, month)[1])
    return moment.replace(year=year, month=month, day=day)


def format_shanghai(moment: datetime) -> str:
    """Serialize a naive UTC timestamp as ISO8601 in Asia/Shanghai."""
    if moment.tzinfo is not None:
        aware = moment.astimezone(_SHANGHAI)
    else:
        aware = moment.replace(tzinfo=UTC).astimezone(_SHANGHAI)
    return aware.isoformat(timespec="seconds")
