from datetime import UTC, datetime


class Clock:
    def now(self) -> datetime:
        return datetime.now(UTC).replace(tzinfo=None)


def get_clock() -> Clock:
    return Clock()
