import pytest

from shipdesk.carriers.base import WeightLimitExceeded
from shipdesk.carriers.fedex import CARRIER


def test_supports_listed_countries_only():
    assert CARRIER.supports("US")
    assert not CARRIER.supports("ZZ")


def test_band_limit_is_inclusive():
    assert CARRIER.estimate_cents(500, "domestic") == CARRIER.rate_table["domestic"][0][1]
    assert CARRIER.estimate_cents(501, "domestic") == CARRIER.rate_table["domestic"][1][1]


def test_heaviest_band_and_overflow():
    top = CARRIER.rate_table["international"][-1]
    assert CARRIER.estimate_cents(top[0], "international") == top[1]
    with pytest.raises(WeightLimitExceeded):
        CARRIER.estimate_cents(top[0] + 1, "international")


def test_transit_and_label():
    assert CARRIER.transit("domestic") == 2
    assert CARRIER.label_code("air").endswith("-AIR")
