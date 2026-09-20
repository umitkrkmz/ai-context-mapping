from shipdesk.analytics.shipping_report import free_shipping_share, shipping_revenue_cents


def test_free_shipping_share():
    rows = [{"shipping_cents": 0}, {"shipping_cents": 599}]
    assert free_shipping_share(rows) == 0.5
    assert free_shipping_share([]) == 0.0


def test_shipping_revenue():
    assert shipping_revenue_cents([{"shipping_cents": 599}, {"shipping_cents": 0}]) == 599
