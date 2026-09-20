import pytest

from shipdesk.cart import Cart
from shipdesk.catalog import UnknownSku


def test_add_and_subtotal():
    cart = Cart()
    cart.add("MUG-01", 2)
    cart.add("PEN-05")
    assert cart.item_count() == 3
    assert cart.subtotal_cents() == 2700


def test_unknown_sku():
    with pytest.raises(UnknownSku):
        Cart().add("NOPE")


def test_quantity_must_be_positive():
    with pytest.raises(ValueError):
        Cart().add("MUG-01", 0)


def test_remove_and_weight():
    cart = Cart()
    cart.add("LMP-04")
    cart.add("PEN-05", 2)
    assert cart.total_weight_grams() == 1840
    cart.remove("LMP-04")
    assert cart.total_weight_grams() == 40
