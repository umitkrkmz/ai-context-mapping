from shipdesk.money import apply_bps, to_cents, to_display


def test_to_cents_rounds_half_up():
    assert to_cents("0.285") == 29
    assert to_cents("12.00") == 1200


def test_to_display():
    assert to_display(1999) == "19.99"
    assert to_display(5) == "0.05"
    assert to_display(-250) == "-2.50"


def test_apply_bps_rounds_half_up():
    assert apply_bps(1000, 725) == 73
    assert apply_bps(0, 500) == 0
