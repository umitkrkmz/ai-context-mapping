import pytest

from shipdesk.services.inventory_service import InsufficientStock, low_stock, release, reserve


def test_reserve_and_release():
    stock = {"A": 5}
    assert reserve(stock, "A", 2) == {"A": 3}
    assert stock == {"A": 5}
    assert release({"A": 3}, "A", 2) == {"A": 5}


def test_reserve_rejects_shortage_and_bad_quantity():
    with pytest.raises(InsufficientStock):
        reserve({"A": 1}, "A", 2)
    with pytest.raises(ValueError):
        reserve({"A": 1}, "A", 0)


def test_low_stock_is_strictly_below():
    assert low_stock({"A": 4, "B": 5, "C": 0}) == ["A", "C"]
