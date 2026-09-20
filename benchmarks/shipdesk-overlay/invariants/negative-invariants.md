# Negative Invariants: ShipDesk

Each entry protects code that looks simplifiable but must not change. Read the entries that a
file's map row lists before you edit that file.

### NI-101: `money.to_cents` keeps `Decimal` with `ROUND_HALF_UP`

- **Protects:** `shipdesk/money.py::to_cents`
- **Looks like:** Over-engineered; `int(round(float(x) * 100))` is shorter.
- **Exists because:** Binary floats turn 0.285 into 28 cents. Prices are rounded half up.
- **Never:** Replace `Decimal` with `float`, or `ROUND_HALF_UP` with `round()`.

```invariant-rule
{
  "id": "NI-101",
  "type": "required-text",
  "description": "to_cents must keep Decimal arithmetic with ROUND_HALF_UP.",
  "file": "shipdesk/money.py",
  "contains": ["INVARIANT(NI-101)", "ROUND_HALF_UP", "Decimal"]
}
```

### NI-102: Money is integer cents; never introduce floats

- **Protects:** every amount, threshold, and total in `shipdesk/`.
- **Exists because:** All thresholds and totals are compared as integers so that results are exact.
- **Never:** Call `float()` in `shipping.py`, `discounts.py`, `tax.py`, `checkout.py`, or
  `cart.py`; do not convert cents to dollars before comparing.

```invariant-rule
{
  "id": "NI-102",
  "type": "forbidden-call",
  "description": "Money code must not call float(); amounts are integer cents.",
  "calls": ["float"],
  "scope": ["shipdesk/shipping.py", "shipdesk/discounts.py", "shipdesk/tax.py", "shipdesk/checkout.py", "shipdesk/cart.py"]
}
```
