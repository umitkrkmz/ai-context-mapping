from shipdesk.reports import daily_summary


def test_daily_summary():
    records = [
        {"total_cents": 1799, "shipping_cents": 599},
        {"total_cents": 9000, "shipping_cents": 0},
    ]
    assert daily_summary(records) == {"orders": 2, "revenue_cents": 10799, "free_shipping_orders": 1}


def test_empty_summary():
    assert daily_summary([]) == {"orders": 0, "revenue_cents": 0, "free_shipping_orders": 0}
