"""Quote computation: ties together cart, discounts, shipping, and tax."""
from typing import Optional

from .cart import Cart
from .discounts import best_discount_cents
from .models import Address, Quote
from .shipping import shipping_cost_cents
from .tax import tax_cents


def compute_quote(cart: Cart, address: Address, coupon: Optional[str] = None) -> Quote:
    subtotal = cart.subtotal_cents()
    discount = best_discount_cents(cart, coupon)
    discounted = subtotal - discount
    shipping = shipping_cost_cents(discounted, cart.total_weight_grams(), address)
    tax = tax_cents(discounted, address.region)
    return Quote(subtotal, discount, shipping, tax, discounted + shipping + tax, coupon)
