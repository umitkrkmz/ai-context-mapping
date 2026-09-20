"""Stock reservation. Stock is a dict of sku -> units on hand."""
from typing import Dict


class InsufficientStock(ValueError):
    pass


def reserve(stock: Dict[str, int], sku: str, quantity: int) -> Dict[str, int]:
    """Return a new stock dict with ``quantity`` units removed; raises when stock is short."""
    if quantity < 1:
        raise ValueError("quantity must be at least 1")
    on_hand = stock.get(sku, 0)
    if on_hand < quantity:
        raise InsufficientStock(f"{sku}: {on_hand} on hand, {quantity} requested")
    updated = dict(stock)
    updated[sku] = on_hand - quantity
    return updated


def release(stock: Dict[str, int], sku: str, quantity: int) -> Dict[str, int]:
    updated = dict(stock)
    updated[sku] = updated.get(sku, 0) + quantity
    return updated


def low_stock(stock: Dict[str, int], threshold: int = 5):
    """SKUs with fewer than ``threshold`` units (strictly below)."""
    return sorted(sku for sku, units in stock.items() if units < threshold)
