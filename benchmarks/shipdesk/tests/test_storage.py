from shipdesk.cart import Cart
from shipdesk.models import Address
from shipdesk.orders import get_order, place_order


def test_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("SHIPDESK_DATA_DIR", str(tmp_path))
    cart = Cart()
    cart.add("MUG-01")
    order_id = place_order(cart, Address("US", "OR"))
    record = get_order(order_id)
    assert record["lines"] == {"MUG-01": 1}
    assert record["shipping_cents"] == 599
