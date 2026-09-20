"""Revenue totals."""
from collections import defaultdict
from typing import Dict, Iterable


def revenue_by_day(records: Iterable[Dict[str, object]]) -> Dict[str, int]:
    totals: Dict[str, int] = defaultdict(int)
    for record in records:
        totals[str(record.get("date", "unknown"))] += int(record["total_cents"])
    return dict(sorted(totals.items()))


def average_order_cents(records: Iterable[Dict[str, object]]) -> int:
    rows = list(records)
    return sum(int(r["total_cents"]) for r in rows) // len(rows) if rows else 0
