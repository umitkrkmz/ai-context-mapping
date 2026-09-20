from shipdesk.analytics.revenue import average_order_cents, revenue_by_day


def test_revenue_by_day_sorted():
    rows = [{"date": "2026-01-02", "total_cents": 200}, {"date": "2026-01-01", "total_cents": 100}, {"date": "2026-01-02", "total_cents": 50}]
    assert list(revenue_by_day(rows).items()) == [("2026-01-01", 100), ("2026-01-02", 250)]


def test_average_handles_empty():
    assert average_order_cents([]) == 0
    assert average_order_cents([{"total_cents": 100}, {"total_cents": 201}]) == 150
