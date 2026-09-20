"""Refund statistics."""
from typing import Dict, Iterable


def refund_rate(orders: int, refunds: int) -> float:
    return 0.0 if orders == 0 else refunds / orders


def refunded_cents(records: Iterable[Dict[str, object]]) -> int:
    return sum(int(r.get("refund_cents", 0)) for r in records)
