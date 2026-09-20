"""US state base sales tax in basis points (state level only; local taxes are not modeled)."""
from ..money import apply_bps

STATE_RATES_BPS = {
    "AL": 400,
    "AK": 0,
    "AZ": 560,
    "AR": 650,
    "CA": 725,
    "CO": 290,
    "CT": 635,
    "DE": 0,
    "FL": 600,
    "GA": 400,
    "HI": 400,
    "ID": 600,
    "IL": 625,
    "IN": 700,
    "IA": 600,
    "KS": 650,
    "KY": 600,
    "LA": 445,
    "ME": 550,
    "MD": 600,
    "MA": 625,
    "MI": 600,
    "MN": 688,
    "MS": 700,
    "MO": 423,
    "MT": 0,
    "NE": 550,
    "NV": 685,
    "NH": 0,
    "NJ": 663,
    "NM": 513,
    "NY": 400,
    "NC": 475,
    "ND": 500,
    "OH": 575,
    "OK": 450,
    "OR": 0,
    "PA": 600,
    "RI": 700,
    "SC": 600,
    "SD": 450,
    "TN": 700,
    "TX": 625,
    "UT": 485,
    "VT": 600,
    "VA": 430,
    "WA": 650,
    "WV": 600,
    "WI": 500,
    "WY": 400,
}
NO_TAX_STATES = frozenset(state for state, bps in STATE_RATES_BPS.items() if bps == 0)


def state_tax_cents(taxable_cents: int, state: str) -> int:
    return apply_bps(taxable_cents, STATE_RATES_BPS[state])


def has_sales_tax(state: str) -> bool:
    return STATE_RATES_BPS[state] > 0
