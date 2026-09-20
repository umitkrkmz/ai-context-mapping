from shipdesk.analytics.refunds import refund_rate, refunded_cents


def test_refund_rate():
    assert refund_rate(0, 3) == 0.0
    assert refund_rate(10, 1) == 0.1


def test_refunded_cents_defaults_to_zero():
    assert refunded_cents([{"refund_cents": 250}, {}]) == 250
