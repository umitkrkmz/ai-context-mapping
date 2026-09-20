"""DHL adapter: rate table and transit times for DHL shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 474), (2000, 759), (5000, 1234), (20000, 2374)],
    "regional": [(500, 759), (2000, 1139), (5000, 1804), (20000, 3324)],
    "international": [(500, 1424), (2000, 2184), (5000, 3609), (20000, 6174)],
}
TRANSIT_DAYS = {"domestic": 3, "regional": 3, "international": 6}


class DHLCarrier(Carrier):
    name = "DHL"
    countries = frozenset(["DE", "FR", "GB", "US", "JP", "AU"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = DHLCarrier()
