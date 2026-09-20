"""Money helpers. Money is always an integer number of cents."""
from decimal import ROUND_HALF_UP, Decimal


def to_cents(amount: str) -> int:
    """Convert a decimal string such as "12.345" to integer cents, rounding half up."""
    # INVARIANT(NI-101): Decimal with ROUND_HALF_UP. float() or round() would turn 0.285 into 28 cents.
    return int((Decimal(amount) * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def to_display(cents: int) -> str:
    """Format integer cents as a plain decimal string, for example 1999 -> "19.99"."""
    sign = "-" if cents < 0 else ""
    whole, fraction = divmod(abs(cents), 100)
    return f"{sign}{whole}.{fraction:02d}"


def apply_bps(cents: int, bps: int) -> int:
    """Return cents * bps / 10000 rounded half up, using integers only."""
    return (cents * bps * 2 + 10000) // 20000
