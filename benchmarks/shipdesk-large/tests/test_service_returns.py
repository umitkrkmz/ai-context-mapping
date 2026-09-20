from shipdesk.services.returns_service import refund_cents, within_window


def test_window_last_day_is_allowed():
    assert within_window(0, 30)
    assert not within_window(0, 31)
    assert within_window(400, 45)


def test_refund_after_fee():
    assert refund_cents(10000, 3) == 10000
    assert refund_cents(10000, 20) == 9000
    assert refund_cents(10000, 45) == 7500
