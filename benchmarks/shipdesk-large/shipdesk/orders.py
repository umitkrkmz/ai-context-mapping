"""Placing and reloading orders."""
import itertools
from typing import Any, Dict, Optional

from .cart import Cart
from .checkout import compute_quote
from .models import Address
from .storage import load_record, save_record

_counter = itertools.count(1)


def place_order(cart: Cart, address: Address, coupon: Optional[str] = None) -> str:
    quote = compute_quote(cart, address, coupon)
    order_id = f"ORD{next(_counter):05d}"
    save_record(
        order_id,
        {
            "country": address.country,
            "region": address.region,
            "lines": {line.item.sku: line.quantity for line in cart.lines()},
            "total_cents": quote.total_cents,
            "shipping_cents": quote.shipping_cents,
        },
    )
    return order_id


def get_order(order_id: str) -> Dict[str, Any]:
    return load_record(order_id)
