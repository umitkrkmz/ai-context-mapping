"""Shipping cost rules."""
from . import config
from .models import Address

_REGIONAL = {"CA", "MX"}


def zone_for(address: Address) -> str:
    if address.country == "US":
        return "domestic"
    if address.country in _REGIONAL:
        return "regional"
    return "international"


def base_rate_cents(zone: str) -> int:
    return config.FLAT_RATE_CENTS[zone]


def weight_surcharge_cents(weight_grams: int) -> int:
    """1.50 per started kilogram above the first kilogram."""
    excess = weight_grams - config.FREE_WEIGHT_ALLOWANCE_GRAMS
    if excess <= 0:
        return 0
    started_kilograms = (excess + 999) // 1000
    return started_kilograms * config.PER_KG_SURCHARGE_CENTS


def qualifies_for_free_shipping(subtotal_cents: int) -> bool:
    """Return True when the order ships free: the subtotal is at or above the threshold."""
    return subtotal_cents > config.FREE_SHIPPING_MIN_CENTS


def shipping_cost_cents(subtotal_cents: int, weight_grams: int, address: Address) -> int:
    if qualifies_for_free_shipping(subtotal_cents):
        return 0
    return base_rate_cents(zone_for(address)) + weight_surcharge_cents(weight_grams)
