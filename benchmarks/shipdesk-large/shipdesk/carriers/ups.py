"""UPS adapter: rate table and transit times for UPS shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 499), (2000, 799), (5000, 1299), (20000, 2499)],
    "regional": [(500, 799), (2000, 1199), (5000, 1899), (20000, 3499)],
    "international": [(500, 1499), (2000, 2299), (5000, 3799), (20000, 6499)],
}
TRANSIT_DAYS = {"domestic": 3, "regional": 4, "international": 9}


class UPSCarrier(Carrier):
    name = "UPS"
    countries = frozenset(["US", "CA", "MX", "DE", "GB"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = UPSCarrier()
