# ShipDesk

A small checkout library: carts, discounts, shipping, tax, and order storage.
Amounts are integer cents everywhere.

```python
from shipdesk.cart import Cart
from shipdesk.checkout import compute_quote
from shipdesk.models import Address

cart = Cart()
cart.add("MUG-01", 2)
quote = compute_quote(cart, Address("US", "CA"))
print(quote.total_cents)
```

Run the tests with `python -m pytest`.
