"""Sales by country and region."""
from collections import defaultdict
from typing import Dict, Iterable, Tuple


def sales_by_region(records: Iterable[Dict[str, object]]) -> Dict[Tuple[str, str], int]:
    totals: Dict[Tuple[str, str], int] = defaultdict(int)
    for record in records:
        totals[(str(record.get("country", "")), str(record.get("region", "")))] += int(record["total_cents"])
    return dict(totals)


def top_region(records: Iterable[Dict[str, object]]):
    totals = sales_by_region(records)
    return max(totals, key=lambda key: totals[key]) if totals else None
