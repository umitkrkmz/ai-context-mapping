"""Sales tax."""
from . import config
from .money import apply_bps


def tax_cents(taxable_cents: int, region: str) -> int:
    return apply_bps(taxable_cents, config.TAX_RATES_BPS.get(region, 0))
