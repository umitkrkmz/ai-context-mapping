"""Input validation."""
import re

from .models import Address

_COUPON = re.compile(r"^[A-Za-z0-9]{4,16}$")


def validate_coupon_format(code: str) -> bool:
    return bool(_COUPON.match(code or ""))


def validate_address(address: Address) -> None:
    if len(address.country) != 2 or not address.country.isalpha():
        raise ValueError("country must be a two-letter code")
    if address.country == "US" and not address.region:
        raise ValueError("US addresses need a region")
