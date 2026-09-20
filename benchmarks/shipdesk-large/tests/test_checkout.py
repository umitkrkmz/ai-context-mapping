from shipdesk.cart import Cart
from shipdesk.checkout import compute_quote
from shipdesk.models import Address


def test_small_order_pays_shipping_and_tax():
    cart = Cart()
    cart.add("MUG-01")
    quote = compute_quote(cart, Address("US", "OR"))
    assert quote.shipping_cents == 599
    assert quote.total_cents == 1200 + 599


def test_large_order_ships_free():
    cart = Cart()
    cart.add("LMP-04", 2)
    quote = compute_quote(cart, Address("US", "OR"))
    assert quote.subtotal_cents == 9000
    assert quote.shipping_cents == 0


def test_coupon_reduces_total():
    cart = Cart()
    cart.add("TEE-02", 4)
    quote = compute_quote(cart, Address("US", "OR"), "WELCOME10")
    assert quote.discount_cents == 1000
    assert quote.total_cents == 9000
