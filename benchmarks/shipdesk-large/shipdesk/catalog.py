"""A tiny in-memory product catalog."""
from typing import Dict

from .models import Item

CATALOG: Dict[str, Item] = {
    "MUG-01": Item("MUG-01", "Enamel mug", 1200, 350),
    "TEE-02": Item("TEE-02", "Logo t-shirt", 2500, 220),
    "BAG-03": Item("BAG-03", "Canvas tote", 1800, 400),
    "LMP-04": Item("LMP-04", "Desk lamp", 4500, 1800),
    "PEN-05": Item("PEN-05", "Gel pen", 300, 20),
}


class UnknownSku(KeyError):
    """Raised when a SKU is not in the catalog."""


def get_item(sku: str) -> Item:
    try:
        return CATALOG[sku]
    except KeyError:
        raise UnknownSku(sku) from None
