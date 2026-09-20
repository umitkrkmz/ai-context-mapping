import pytest

from shipdesk.services.gift_cards import InsufficientBalance, redeem, top_up


def test_redeem_to_exactly_zero():
    assert redeem(1000, 1000) == 0


def test_redeem_rejects_overdraw_and_negative():
    with pytest.raises(InsufficientBalance):
        redeem(1000, 1001)
    with pytest.raises(ValueError):
        redeem(1000, -1)


def test_top_up_caps():
    assert top_up(49000, 5000) == 50000
