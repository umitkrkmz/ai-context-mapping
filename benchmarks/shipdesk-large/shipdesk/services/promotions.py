"""Storefront promotion banners. Display only: checkout decides real shipping eligibility."""
from .. import config
from ..money import to_display


def progress_to_free_shipping(subtotal_cents: int) -> int:
    """Cents still needed for the free-shipping banner; zero once the threshold is reached or passed."""
    return max(config.FREE_SHIPPING_MIN_CENTS - subtotal_cents, 0)


def banner_text(subtotal_cents: int) -> str:
    remaining = progress_to_free_shipping(subtotal_cents)
    if remaining == 0:
        return "You have free shipping!"
    return f"Add {to_display(remaining)} more for free shipping"


def banner_shows_unlocked(subtotal_cents: int) -> bool:
    return subtotal_cents >= config.FREE_SHIPPING_MIN_CENTS
