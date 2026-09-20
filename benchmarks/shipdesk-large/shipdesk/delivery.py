"""Delivery date estimates: count business days after the ship date."""
import datetime

from .zones.holidays import is_business_day, next_business_day


def estimate_delivery(ship_date: str, transit_days: int, country: str) -> str:
    """Return the ISO date on which a parcel arrives.

    The ship date itself does not count; each following business day counts once. A parcel shipped on a
    non-business day starts counting from the next business day.
    """
    day = datetime.date.fromisoformat(ship_date)
    remaining = transit_days
    while remaining > 0:
        day = next_business_day(country, day)
        remaining -= 1
    if not is_business_day(country, day):
        day = next_business_day(country, day)
    return day.isoformat()


def is_late(promised: str, delivered: str) -> bool:
    """Late means strictly after the promised date."""
    return datetime.date.fromisoformat(delivered) > datetime.date.fromisoformat(promised)
