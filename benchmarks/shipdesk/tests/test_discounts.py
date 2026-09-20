from shipdesk.cart import Cart
from shipdesk.discounts import best_discount_cents, bulk_discount_cents, coupon_discount_cents


def test_bulk_discount_starts_at_ten_items():
    cart = Cart()
    cart.add("PEN-05", 9)
    assert bulk_discount_cents(cart) == 0
    cart.add("PEN-05")
    assert bulk_discount_cents(cart) == 150


def test_coupon_is_case_insensitive():
    assert coupon_discount_cents(10000, "welcome10") == 1000
    assert coupon_discount_cents(10000, "UNKNOWN") == 0
    assert coupon_discount_cents(10000, None) == 0


def test_discounts_never_stack():
    cart = Cart()
    cart.add("PEN-05", 10)
    assert best_discount_cents(cart, "WELCOME10") == 300
