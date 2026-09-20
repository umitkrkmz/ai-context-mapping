"""EU VAT: standard and reduced rates in basis points per member state."""
from dataclasses import dataclass
from typing import Dict

from ..money import apply_bps


@dataclass(frozen=True)
class VatRate:
    country: str
    standard_bps: int
    reduced_bps: int


VAT_RATES: Dict[str, VatRate] = {
    "AT": VatRate("Austria", 2000, 1000),
    "BE": VatRate("Belgium", 2100, 600),
    "BG": VatRate("Bulgaria", 2000, 900),
    "HR": VatRate("Croatia", 2500, 1300),
    "CY": VatRate("Cyprus", 1900, 900),
    "CZ": VatRate("Czechia", 2100, 1200),
    "DK": VatRate("Denmark", 2500, 2500),
    "EE": VatRate("Estonia", 2200, 900),
    "FI": VatRate("Finland", 2550, 1400),
    "FR": VatRate("France", 2000, 550),
    "DE": VatRate("Germany", 1900, 700),
    "GR": VatRate("Greece", 2400, 1300),
    "HU": VatRate("Hungary", 2700, 1800),
    "IE": VatRate("Ireland", 2300, 900),
    "IT": VatRate("Italy", 2200, 1000),
    "LV": VatRate("Latvia", 2100, 1200),
    "LT": VatRate("Lithuania", 2100, 900),
    "LU": VatRate("Luxembourg", 1700, 800),
    "MT": VatRate("Malta", 1800, 700),
    "NL": VatRate("Netherlands", 2100, 900),
    "PL": VatRate("Poland", 2300, 800),
    "PT": VatRate("Portugal", 2300, 1300),
    "RO": VatRate("Romania", 1900, 900),
    "SK": VatRate("Slovakia", 2000, 1000),
    "SI": VatRate("Slovenia", 2200, 950),
    "ES": VatRate("Spain", 2100, 1000),
    "SE": VatRate("Sweden", 2500, 1200),
}
REDUCED_CATEGORIES = {"books", "food", "medicine"}


def rate_bps(country: str, category: str = "general") -> int:
    rate = VAT_RATES[country]
    return rate.reduced_bps if category in REDUCED_CATEGORIES else rate.standard_bps


def vat_cents(net_cents: int, country: str, category: str = "general") -> int:
    return apply_bps(net_cents, rate_bps(country, category))


def gross_cents(net_cents: int, country: str, category: str = "general") -> int:
    return net_cents + vat_cents(net_cents, country, category)


def net_from_gross(gross: int, country: str, category: str = "general") -> int:
    """Invert gross_cents, rounding half up on the net amount."""
    bps = rate_bps(country, category)
    return (gross * 20000 + (10000 + bps)) // (2 * (10000 + bps))
