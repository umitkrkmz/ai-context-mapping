"""Return eligibility and refund amounts."""
from ..money import apply_bps
from ..tiers import restocking_fee, return_window


def within_window(tenure_days: int, days_since_delivery: int) -> bool:
    """A return is allowed up to and including the last day of the customer's return window."""
    return days_since_delivery <= return_window.benefit_for(tenure_days)


def refund_cents(paid_cents: int, days_since_delivery: int) -> int:
    fee_bps = restocking_fee.benefit_for(days_since_delivery)
    return paid_cents - apply_bps(paid_cents, fee_bps)
