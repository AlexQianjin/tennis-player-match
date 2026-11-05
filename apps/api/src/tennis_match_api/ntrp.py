from decimal import Decimal, InvalidOperation

_STEP = Decimal("0.1")
_MIN = Decimal("1.0")
_MAX = Decimal("7.0")


def parse_ntrp(value: object) -> Decimal:
    """Return an NTRP on the 0.5 grid from 1.0 through 7.0."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str, Decimal)):
        raise ValueError("ntrp must be between 1.0 and 7.0 in steps of 0.5")
    raw = value.strip() if isinstance(value, str) else value
    try:
        number = Decimal(str(raw)).quantize(_STEP)
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("ntrp must be between 1.0 and 7.0 in steps of 0.5") from exc
    scaled = int((number * 10).to_integral_value())
    if number < _MIN or number > _MAX or scaled % 5 != 0:
        raise ValueError("ntrp must be between 1.0 and 7.0 in steps of 0.5")
    return number


def same_ntrp(left: Decimal | None, right: Decimal | None) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return left.quantize(_STEP) == right.quantize(_STEP)
