"""Deprecated since 1.4.0. Kept only for the old CSV importer; checkout does not use it."""


def free_shipping(total_cents: int) -> bool:
    """Old free-shipping test used by the importer (threshold 50.00)."""
    return total_cents > 5000
