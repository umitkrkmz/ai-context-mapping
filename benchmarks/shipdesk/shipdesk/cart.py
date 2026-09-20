"""Shopping cart."""
from typing import Dict, List

from .catalog import get_item
from .models import CartLine


class Cart:
    def __init__(self) -> None:
        self._quantities: Dict[str, int] = {}

    def add(self, sku: str, quantity: int = 1) -> None:
        if quantity < 1:
            raise ValueError("quantity must be at least 1")
        get_item(sku)
        self._quantities[sku] = self._quantities.get(sku, 0) + quantity

    def remove(self, sku: str) -> None:
        self._quantities.pop(sku, None)

    def lines(self) -> List[CartLine]:
        return [CartLine(get_item(sku), qty) for sku, qty in sorted(self._quantities.items())]

    def item_count(self) -> int:
        return sum(self._quantities.values())

    def subtotal_cents(self) -> int:
        return sum(line.item.unit_cents * line.quantity for line in self.lines())

    def total_weight_grams(self) -> int:
        return sum(line.item.weight_grams * line.quantity for line in self.lines())
