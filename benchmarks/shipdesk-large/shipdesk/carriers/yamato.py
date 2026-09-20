"""Yamato adapter: rate table and transit times for YAMATO shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 598), (2000, 958), (5000, 1558), (20000, 2998)],
    "regional": [(500, 958), (2000, 1438), (5000, 2278), (20000, 4198)],
    "international": [(500, 1798), (2000, 2758), (5000, 4558), (20000, 7798)],
}
TRANSIT_DAYS = {"domestic": 2, "regional": 5, "international": 8}


class YamatoCarrier(Carrier):
    name = "Yamato"
    countries = frozenset(["JP", "US", "AU"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = YamatoCarrier()
