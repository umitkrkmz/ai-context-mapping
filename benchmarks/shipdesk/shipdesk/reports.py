"""Order reports."""
from typing import Dict, Iterable


def daily_summary(records: Iterable[Dict[str, int]]) -> Dict[str, int]:
    count = 0
    revenue = 0
    free_shipping = 0
    for record in records:
        count += 1
        revenue += record["total_cents"]
        if record["shipping_cents"] == 0:
            free_shipping += 1
    return {"orders": count, "revenue_cents": revenue, "free_shipping_orders": free_shipping}
