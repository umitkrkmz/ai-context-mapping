"""CanadaPost adapter: rate table and transit times for CANADAPOST shipments."""
from .base import Carrier

RATE_TABLE = {
    "domestic": [(500, 424), (2000, 679), (5000, 1104), (20000, 2124)],
    "regional": [(500, 679), (2000, 1019), (5000, 1614), (20000, 2974)],
    "international": [(500, 1274), (2000, 1954), (5000, 3229), (20000, 5524)],
}
TRANSIT_DAYS = {"domestic": 4, "regional": 6, "international": 11}


class CanadaPostCarrier(Carrier):
    name = "CanadaPost"
    countries = frozenset(["CA", "US"])
    rate_table = RATE_TABLE
    transit_days = TRANSIT_DAYS


CARRIER = CanadaPostCarrier()
