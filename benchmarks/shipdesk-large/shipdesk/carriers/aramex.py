"""Aramex adapter: rate table and transit times for ARAMEX shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 548), (2000, 878), (5000, 1428), (20000, 2748)],
    "regional": [(500, 878), (2000, 1318), (5000, 2088), (20000, 3848)],
    "international": [(500, 1648), (2000, 2528), (5000, 4178), (20000, 7148)],
}
TRANSIT_DAYS = {"domestic": 4, "regional": 5, "international": 9}


class AramexCarrier(Carrier):
    name = "Aramex"
    countries = frozenset(["AE", "SA", "GB", "US"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = AramexCarrier()
