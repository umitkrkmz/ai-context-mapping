from shipdesk.analytics.top_products import top_skus


def test_top_skus_orders_by_quantity_then_name():
    rows = [{"lines": {"B": 2, "A": 2}}, {"lines": {"C": 1}}]
    assert top_skus(rows, 2) == [("A", 2), ("B", 2)]


def test_top_skus_handles_missing_lines():
    assert top_skus([{}]) == []
