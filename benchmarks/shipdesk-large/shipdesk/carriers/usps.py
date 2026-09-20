"""USPS adapter: rate table and transit times for USPS shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 399), (2000, 639), (5000, 1039), (20000, 1999)],
    "regional": [(500, 639), (2000, 959), (5000, 1519), (20000, 2799)],
    "international": [(500, 1199), (2000, 1839), (5000, 3039), (20000, 5199)],
}
TRANSIT_DAYS = {"domestic": 3, "regional": 5, "international": 12}


class USPSCarrier(Carrier):
    name = "USPS"
    countries = frozenset(["US"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = USPSCarrier()
