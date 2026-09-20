"""Bulk and coupon discounts."""
from typing import Optional

from . import config
from .cart import Cart
from .money import apply_bps


def bulk_discount_cents(cart: Cart) -> int:
    if cart.item_count() < config.BULK_DISCOUNT_MIN_ITEMS:
        return 0
    return apply_bps(cart.subtotal_cents(), config.BULK_DISCOUNT_BPS)


def coupon_discount_cents(subtotal_cents: int, code: Optional[str]) -> int:
    if not code:
        return 0
    bps = config.COUPONS_BPS.get(code.strip().upper())
    return apply_bps(subtotal_cents, bps) if bps else 0


def best_discount_cents(cart: Cart, code: Optional[str]) -> int:
    """The larger of the bulk and coupon discounts; they never stack."""
    return max(bulk_discount_cents(cart), coupon_discount_cents(cart.subtotal_cents(), code))
