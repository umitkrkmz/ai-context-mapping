"""FedEx adapter: rate table and transit times for FEDEX shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 523), (2000, 838), (5000, 1363), (20000, 2623)],
    "regional": [(500, 838), (2000, 1258), (5000, 1993), (20000, 3673)],
    "international": [(500, 1573), (2000, 2413), (5000, 3988), (20000, 6823)],
}
TRANSIT_DAYS = {"domestic": 2, "regional": 4, "international": 8}


class FedExCarrier(Carrier):
    name = "FedEx"
    countries = frozenset(["US", "CA", "GB", "FR", "JP"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = FedExCarrier()
