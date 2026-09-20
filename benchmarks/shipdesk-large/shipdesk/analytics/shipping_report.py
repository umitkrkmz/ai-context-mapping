"""Shipping revenue and free-shipping share."""
from typing import Dict, Iterable


def free_shipping_share(records: Iterable[Dict[str, object]]) -> float:
    """Fraction of orders whose recorded shipping charge was zero (reporting only; it does not decide eligibility)."""
    rows = list(records)
    if not rows:
        return 0.0
    return sum(1 for r in rows if int(r["shipping_cents"]) == 0) / len(rows)


def shipping_revenue_cents(records: Iterable[Dict[str, object]]) -> int:
    return sum(int(r["shipping_cents"]) for r in records)
