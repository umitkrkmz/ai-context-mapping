# Tier tables

Every module in `shipdesk/tiers/` classifies a value against ascending thresholds. **The comparison
is not the same in every table.** Each was specified by its business owner; changing an operator to
make the tables look consistent changes customer-visible results.

| Module | Rule | Unit | Purpose |
| ------ | ---- | ---- | ------- |
| `tiers/loyalty.py` | inclusive (at or above) | points | Loyalty tier by lifetime points; benefit is a discount in basis points. |
| `tiers/handling_fee.py` | strict (more than) | grams | Handling surcharge by parcel weight; heavy means MORE than 20 kg (strict). |
| `tiers/insurance.py` | inclusive (at or above) | cents | Insurance premium by declared value in cents. |
| `tiers/gift_wrap.py` | strict (more than) | items | Per-item gift wrap price by item count; multi means MORE than 3 items (strict). |
| `tiers/volume_pricing.py` | inclusive (at or above) | units | Wholesale discount in basis points by units per order. |
| `tiers/return_window.py` | strict (more than) | days | Return window in days by customer tenure; valued means MORE than 365 days (strict). |
| `tiers/fraud_bands.py` | inclusive (at or above) | score | Fraud action by risk score; a score at the threshold triggers the band. |
| `tiers/sla_priority.py` | strict (more than) | hours | Support priority by ticket age in hours; p2 means MORE than 24 hours (strict). |
| `tiers/delivery_speed.py` | inclusive (at or above) | days | Delivery surcharge by promised days; fee in cents (negative is a discount). |
| `tiers/restocking_fee.py` | strict (more than) | days | Restocking fee in basis points by days since delivery; partial means MORE than 14 days (strict). |

Shipping eligibility is **not** a tier table. It is a single rule in `shipdesk/shipping.py` governed by
`docs/pricing-policy.md`.
