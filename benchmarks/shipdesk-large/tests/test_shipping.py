from shipdesk.models import Address
from shipdesk.shipping import (
    base_rate_cents,
    qualifies_for_free_shipping,
    shipping_cost_cents,
    weight_surcharge_cents,
    zone_for,
)


def test_zones():
    assert zone_for(Address("US", "CA")) == "domestic"
    assert zone_for(Address("MX")) == "regional"
    assert zone_for(Address("DE")) == "international"


def test_base_rates():
    assert base_rate_cents("domestic") == 599
    assert base_rate_cents("international") == 1999


def test_weight_surcharge():
    assert weight_surcharge_cents(1000) == 0
    assert weight_surcharge_cents(1001) == 150
    assert weight_surcharge_cents(2500) == 300


def test_free_shipping_for_large_orders():
    assert qualifies_for_free_shipping(9000)


def test_paid_shipping_for_small_orders():
    assert not qualifies_for_free_shipping(1000)


def test_shipping_cost_for_small_light_order():
    assert shipping_cost_cents(1000, 500, Address("US", "CA")) == 599
