"""Carrier lookup and cheapest-carrier selection."""
from typing import Dict, List, Optional

from . import aramex, canada_post, dhl, fedex, royal_mail, ups, usps, yamato
from .base import Carrier, WeightLimitExceeded

_ALL: List[Carrier] = [
    ups.CARRIER, fedex.CARRIER, dhl.CARRIER, usps.CARRIER,
    royal_mail.CARRIER, canada_post.CARRIER, aramex.CARRIER, yamato.CARRIER,
]
REGISTRY: Dict[str, Carrier] = {carrier.name.lower(): carrier for carrier in _ALL}


def get_carrier(name: str) -> Carrier:
    return REGISTRY[name.lower()]


def carriers_for(country: str) -> List[Carrier]:
    return [carrier for carrier in _ALL if carrier.supports(country)]


def cheapest(weight_grams: int, zone: str, country: str) -> Optional[Carrier]:
    """Cheapest carrier that serves ``country`` and can carry the parcel; ties keep registry order."""
    best: Optional[Carrier] = None
    best_cents = 0
    for carrier in carriers_for(country):
        try:
            cents = carrier.estimate_cents(weight_grams, zone)
        except WeightLimitExceeded:
            continue
        if best is None or cents < best_cents:
            best, best_cents = carrier, cents
    return best
