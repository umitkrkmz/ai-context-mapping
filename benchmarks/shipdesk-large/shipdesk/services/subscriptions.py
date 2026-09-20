"""Recurring orders: next ship date arithmetic on ISO dates."""
import datetime

INTERVALS = {"weekly": 7, "biweekly": 14, "monthly": 30}


def next_ship_date(last_shipped: str, interval: str) -> str:
    date = datetime.date.fromisoformat(last_shipped)
    return (date + datetime.timedelta(days=INTERVALS[interval])).isoformat()


def is_due(next_date: str, today: str) -> bool:
    """A subscription is due on its ship date and every day after it."""
    return datetime.date.fromisoformat(today) >= datetime.date.fromisoformat(next_date)
