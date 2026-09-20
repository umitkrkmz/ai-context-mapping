"""Plain data containers shared by the other modules."""
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass(frozen=True)
class Item:
    sku: str
    name: str
    unit_cents: int
    weight_grams: int


@dataclass
class CartLine:
    item: Item
    quantity: int


@dataclass(frozen=True)
class Address:
    country: str
    region: str = ""


@dataclass
class Quote:
    subtotal_cents: int
    discount_cents: int
    shipping_cents: int
    tax_cents: int
    total_cents: int
    coupon: Optional[str] = None


@dataclass
class Order:
    order_id: str
    lines: List[CartLine] = field(default_factory=list)
    quote: Optional[Quote] = None
    country: str = ""
