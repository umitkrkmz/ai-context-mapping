# Project Map: ShipDesk

> Read this file before running exploratory `grep` or `find` commands.
> Every non-ignored path has one row. `Invariants` lists IDs defined in `invariants/negative-invariants.md`; read them before editing the file.

## File Index

| Path | Category | Purpose | Invariants |
| ---- | -------- | ------- | ---------- |
| `.agentignore` | ignore | Paths agents must not read. | - |
| `AGENTS.md` | manifesto | Operating manifesto for AI agents: the five rules and Python conventions. | - |
| `CHANGELOG.md` | docs | Release history of ShipDesk. | - |
| `CLAUDE.md` | manifesto | Identical copy of AGENTS.md for Claude Code. | - |
| `README.md` | docs | ShipDesk overview and a usage example. | - |
| `docs/` | docs | Business documentation. | - |
| `docs/pricing-policy.md` | docs | Business rules for discounts, shipping, and tax, owned by merchandising. | - |
| `invariants/` | invariant | Negative invariants. | - |
| `invariants/negative-invariants.md` | invariant | NI-101 and NI-102: money rounding and integer-cents rules. | NI-101, NI-102 |
| `maps/` | map | Repository navigation maps. | - |
| `maps/project-map.md` | map | This file: index of every path with category, purpose, and invariants. | - |
| `mcp/**` | integration | MCP context server (read_project_map, get_file_purpose). | - |
| `scripts/**` | script | Guardrail scripts: init_mapping, verify_invariants, mutation_guard, dependency budget. | - |
| `shipdesk/` | source | The ShipDesk package. | - |
| `shipdesk/__init__.py` | source | Package marker and version string. | - |
| `shipdesk/cart.py` | source | Cart: add and remove SKUs; subtotal, item count, and weight. | NI-102 |
| `shipdesk/catalog.py` | source | In-memory product catalog and UnknownSku error. | - |
| `shipdesk/checkout.py` | source | compute_quote: subtotal, discount, shipping, tax, and total for a cart. | NI-102 |
| `shipdesk/cli.py` | source | Command-line entry point that prints a quote for SKU:QTY arguments. | - |
| `shipdesk/config.py` | source | Business constants: thresholds, rates, tax table, coupons, in cents or basis points. | - |
| `shipdesk/discounts.py` | source | Bulk and coupon discounts; the larger applies, never both. | NI-102 |
| `shipdesk/formatting.py` | source | Formats a Quote as aligned text lines. | - |
| `shipdesk/legacy_shipping.py` | source | Deprecated helper kept for the old CSV importer; not used by checkout. | - |
| `shipdesk/models.py` | source | Data classes: Item, CartLine, Address, Quote, Order. | - |
| `shipdesk/money.py` | source | Integer-cents helpers: to_cents, to_display, apply_bps. | NI-101, NI-102 |
| `shipdesk/orders.py` | source | place_order and get_order on top of the file store. | - |
| `shipdesk/reports.py` | source | daily_summary over stored order records. | - |
| `shipdesk/shipping.py` | source | Shipping zones, base rates, weight surcharge, and the free-shipping rule. | NI-102 |
| `shipdesk/storage.py` | source | One JSON file per order in the data directory. | - |
| `shipdesk/tax.py` | source | Sales tax by region on the discounted subtotal. | NI-102 |
| `shipdesk/validators.py` | source | Address and coupon-format validation. | - |
| `tests/` | test | Test suite. | - |
| `tests/conftest.py` | test | Puts the project root on sys.path for the tests. | - |
| `tests/test_cart.py` | test | Tests for the cart. | - |
| `tests/test_checkout.py` | test | Integration tests for compute_quote. | - |
| `tests/test_discounts.py` | test | Tests for bulk and coupon discounts. | - |
| `tests/test_formatting.py` | test | Tests for quote formatting. | - |
| `tests/test_maps.py` | test | Fails when a path is missing from the map or CLAUDE.md drifts from AGENTS.md. | - |
| `tests/test_money.py` | test | Tests for money helpers. | - |
| `tests/test_reports.py` | test | Tests for daily_summary. | - |
| `tests/test_shipping.py` | test | Tests for zones, rates, surcharge, and free shipping. | - |
| `tests/test_storage.py` | test | Order round-trip through the file store. | - |
| `tests/test_tax.py` | test | Tests for sales tax. | - |
| `tests/test_validators.py` | test | Tests for validators. | - |
