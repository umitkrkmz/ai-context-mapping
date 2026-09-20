"""Retention: how long each category of record is kept. Ages are in whole days."""
RETENTION_DAYS = {"orders": 2555, "audit": 365, "sessions": 30, "exports": 7}


def is_expired(category: str, age_days: int) -> bool:
    """A record expires once it is OLDER than the retention period (strict: exactly N days is kept)."""
    return age_days > RETENTION_DAYS[category]


def expired(records, category: str):
    return [record for record in records if is_expired(category, record["age_days"])]
