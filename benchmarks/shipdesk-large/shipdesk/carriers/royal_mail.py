"""RoyalMail adapter: rate table and transit times for ROYALMAIL shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 449), (2000, 719), (5000, 1169), (20000, 2249)],
    "regional": [(500, 719), (2000, 1079), (5000, 1709), (20000, 3149)],
    "international": [(500, 1349), (2000, 2069), (5000, 3419), (20000, 5849)],
}
TRANSIT_DAYS = {"domestic": 2, "regional": 4, "international": 10}


class RoyalMailCarrier(Carrier):
    name = "RoyalMail"
    countries = frozenset(["GB", "FR", "DE"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = RoyalMailCarrier()
