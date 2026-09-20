# Architecture

ShipDesk is layered:

1. `models`, `config`, `money`: data classes, business constants, integer-cents helpers.
2. `catalog`, `cart`: what is being bought.
3. `discounts`, `shipping`, `tax`, `checkout`: pricing. `checkout.compute_quote` is the single entry point.
4. `carriers`: rate tables and carrier selection for the physical shipment.
5. `tiers`: threshold tables used by services (loyalty, fraud, returns, fees).
6. `services`, `repos`, `analytics`, `exporters`, `notifications`, `regions`: everything around pricing.

Rules of thumb: money is integer cents; storage is one JSON file per entity kind; no database.
