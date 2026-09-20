import datetime

from shipdesk.delivery import estimate_delivery, is_late
from shipdesk.zones.holidays import HOLIDAYS_2026, is_business_day, is_holiday, next_business_day


def test_holiday_lookup():
    assert is_holiday("US", datetime.date(2026, 12, 25))
    assert not is_holiday("US", datetime.date(2026, 12, 24))
    assert not is_holiday("XX", datetime.date(2026, 12, 25))
    assert set(HOLIDAYS_2026) == {"US", "CA", "GB", "DE", "FR", "JP", "AU", "BR"}


def test_business_days():
    assert is_business_day("US", datetime.date(2026, 3, 2))
    assert not is_business_day("US", datetime.date(2026, 3, 1))
    assert next_business_day("US", datetime.date(2026, 3, 6)) == datetime.date(2026, 3, 9)


def test_estimate_skips_weekends_and_holidays():
    assert estimate_delivery("2026-03-02", 3, "US") == "2026-03-05"
    assert estimate_delivery("2026-03-05", 3, "US") == "2026-03-10"
    assert estimate_delivery("2026-12-23", 2, "US") == "2026-12-28"


def test_zero_transit_on_business_day_is_same_day():
    assert estimate_delivery("2026-03-02", 0, "US") == "2026-03-02"


def test_lateness_is_strict():
    assert not is_late("2026-03-05", "2026-03-05")
    assert is_late("2026-03-05", "2026-03-06")
