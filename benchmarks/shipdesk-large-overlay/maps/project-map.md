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
| `docs/` | docs | Business and architecture documentation | - |
| `docs/adr/**` | docs | Six ADRs: integer cents, JSON store, per-table tiers, checkout entry point, frozen legacy shipping, display vs decision. | - |
| `docs/api.md` | docs | Short public API reference. | - |
| `docs/architecture.md` | docs | Layered overview of the packages. | - |
| `docs/carriers/**` | docs | One short note per carrier adapter. | - |
| `docs/carriers.md` | docs | Carrier rate-table conventions. | - |
| `docs/faq.md` | docs | Frequently asked questions. | - |
| `docs/glossary.md` | docs | Glossary of pricing terms. | - |
| `docs/onboarding.md` | docs | New-contributor guide. | - |
| `docs/pricing-policy.md` | docs | Business rules for discounts, shipping, and tax, owned by merchandising. | - |
| `docs/runbook.md` | docs | Operational troubleshooting notes. | - |
| `docs/tiers/**` | docs | One page per tier table stating its exact inclusive or strict rule in words. | - |
| `docs/tiers.md` | docs | Documents the inclusive or strict rule of every tier table. | - |
| `invariants/` | invariant | Negative invariants. | - |
| `invariants/negative-invariants.md` | invariant | NI-101 to NI-104: money rounding, integer cents, tier operators, frozen legacy module. | NI-101, NI-102, NI-103, NI-104 |
| `maps/` | map | Repository navigation maps. | - |
| `maps/project-map.md` | map | This file: index of every path with category, purpose, and invariants. | - |
| `mcp/**` | integration | MCP context server (read_project_map, get_file_purpose). | - |
| `scripts/**` | script | Guardrail scripts: init_mapping, verify_invariants, mutation_guard, dependency budget. | - |
| `shipdesk/` | source | The ShipDesk package | - |
| `shipdesk/__init__.py` | source | Package marker and version string. | - |
| `shipdesk/analytics/` | source | Package of order reports | - |
| `shipdesk/analytics/__init__.py` | source | Package of order reports. | - |
| `shipdesk/analytics/cohorts.py` | source | Customer cohorts by first-order month. | - |
| `shipdesk/analytics/refunds.py` | source | Refund statistics. | - |
| `shipdesk/analytics/regions_report.py` | source | Sales by country and region. | - |
| `shipdesk/analytics/revenue.py` | source | Revenue totals. | - |
| `shipdesk/analytics/shipping_report.py` | source | Shipping revenue and free-shipping share. | - |
| `shipdesk/analytics/top_products.py` | source | Best-selling SKUs. | - |
| `shipdesk/audit/` | source | Package for audit logging and retention | - |
| `shipdesk/audit/__init__.py` | source | Package for audit logging and retention. | - |
| `shipdesk/audit/log.py` | source | Audit log line format and parser. | - |
| `shipdesk/audit/retention.py` | source | Retention periods per record category; a record expires only when strictly older than the period. | NI-103 |
| `shipdesk/carriers/` | source | Package of carrier adapters and the registry that selects among them | - |
| `shipdesk/carriers/__init__.py` | source | Package of carrier adapters and the registry that selects among them. | - |
| `shipdesk/carriers/aramex.py` | source | Aramex carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/carriers/base.py` | source | Base Carrier class: weight-band pricing (limit is inclusive), support check, label code. | - |
| `shipdesk/carriers/canada_post.py` | source | CanadaPost carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/carriers/dhl.py` | source | DHL carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/carriers/fedex.py` | source | FedEx carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/carriers/registry.py` | source | Carrier registry: lookup by name or country and cheapest-carrier selection. | - |
| `shipdesk/carriers/royal_mail.py` | source | RoyalMail carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/carriers/ups.py` | source | UPS carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/carriers/usps.py` | source | USPS carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/carriers/yamato.py` | source | Yamato carrier: inclusive weight-band rates and transit days. | - |
| `shipdesk/cart.py` | source | Cart: add and remove SKUs; subtotal, item count, and weight. | NI-102 |
| `shipdesk/catalog.py` | source | In-memory product catalog and UnknownSku error. | - |
| `shipdesk/catalog_seed.py` | source | Seed catalog of 100 demo products. | - |
| `shipdesk/checkout.py` | source | compute_quote: subtotal, discount, shipping, tax, and total for a cart. | NI-102 |
| `shipdesk/cli.py` | source | Command-line entry point that prints a quote for SKU:QTY arguments. | - |
| `shipdesk/config.py` | source | Business constants: thresholds, rates, tax table, coupons, in cents or basis points. | - |
| `shipdesk/delivery.py` | source | Business-day delivery estimates using holiday calendars; lateness is strictly after the promise. | - |
| `shipdesk/discounts.py` | source | Bulk and coupon discounts; the larger applies, never both. | NI-102 |
| `shipdesk/exporters/` | source | Package of order exporters and the shared field list | - |
| `shipdesk/exporters/__init__.py` | source | Package of order exporters and the shared field list. | - |
| `shipdesk/exporters/csv_export.py` | source | CSV exporter. | - |
| `shipdesk/exporters/html_export.py` | source | HTML table exporter. | - |
| `shipdesk/exporters/json_export.py` | source | JSON exporter. | - |
| `shipdesk/exporters/markdown_export.py` | source | Markdown table exporter. | - |
| `shipdesk/exporters/tsv_export.py` | source | TSV exporter. | - |
| `shipdesk/exporters/xml_export.py` | source | XML exporter. | - |
| `shipdesk/formatting.py` | source | Formats a Quote as aligned text lines. | - |
| `shipdesk/i18n/` | source | Package of currency formatting helpers | - |
| `shipdesk/i18n/__init__.py` | source | Package of currency formatting helpers. | - |
| `shipdesk/i18n/currency.py` | source | Currency table (24 currencies), amount formatting, and fixed reference conversion. | - |
| `shipdesk/integrations/` | source | Package of external-system field mappings | - |
| `shipdesk/integrations/__init__.py` | source | Package of external-system field mappings. | - |
| `shipdesk/integrations/accounting_export.py` | source | Accounting field mapping in both directions. | - |
| `shipdesk/integrations/crm_sync.py` | source | CRM field mapping in both directions. | - |
| `shipdesk/integrations/erp_sync.py` | source | ERP field mapping in both directions. | - |
| `shipdesk/integrations/marketplace_feed.py` | source | Marketplace field mapping in both directions. | - |
| `shipdesk/legacy_shipping.py` | source | Deprecated helper kept for the old CSV importer; not used by checkout. | NI-104 |
| `shipdesk/models.py` | source | Data classes: Item, CartLine, Address, Quote, Order. | - |
| `shipdesk/money.py` | source | Integer-cents helpers: to_cents, to_display, apply_bps. | NI-101, NI-102 |
| `shipdesk/notifications/` | source | Package of notification templates | - |
| `shipdesk/notifications/__init__.py` | source | Package of notification templates. | - |
| `shipdesk/notifications/email_templates.py` | source | Email order confirmation text. | - |
| `shipdesk/notifications/locale_strings.py` | source | Translated message fragments (en, de, fr, es) with English fallback. | - |
| `shipdesk/notifications/push_templates.py` | source | Push notification payload for refunds. | - |
| `shipdesk/notifications/sms_templates.py` | source | SMS shipped message, truncated to 160 characters. | - |
| `shipdesk/notifications/webhook_payloads.py` | source | Webhook JSON payload with sorted keys. | - |
| `shipdesk/orders.py` | source | place_order and get_order on top of the file store. | - |
| `shipdesk/regions/` | source | Package of country-specific address helpers | - |
| `shipdesk/regions/__init__.py` | source | Package of country-specific address helpers. | - |
| `shipdesk/regions/au.py` | source | Australia postal code, phone, and address layout helpers. | - |
| `shipdesk/regions/br.py` | source | Brazil postal code, phone, and address layout helpers. | - |
| `shipdesk/regions/ca.py` | source | Canada postal code, phone, and address layout helpers. | - |
| `shipdesk/regions/de.py` | source | Germany postal code, phone, and address layout helpers. | - |
| `shipdesk/regions/fr.py` | source | France postal code, phone, and address layout helpers. | - |
| `shipdesk/regions/gb.py` | source | United Kingdom postal code, phone, and address layout helpers. | - |
| `shipdesk/regions/jp.py` | source | Japan postal code, phone, and address layout helpers. | - |
| `shipdesk/regions/us.py` | source | United States postal code, phone, and address layout helpers. | - |
| `shipdesk/reports.py` | source | daily_summary over stored order records. | - |
| `shipdesk/repos/` | source | Package of file-backed repositories | - |
| `shipdesk/repos/__init__.py` | source | Package of file-backed repositories. | - |
| `shipdesk/repos/base.py` | source | JsonRepo base class: put, get, delete, and list records in one JSON file. | - |
| `shipdesk/repos/coupons.py` | source | Coupon records keyed by id; lookup by code, case-insensitive. | - |
| `shipdesk/repos/customers.py` | source | Customer records keyed by id; lookup by email. | - |
| `shipdesk/repos/inventory.py` | source | Stock records keyed by SKU; lookup by SKU. | - |
| `shipdesk/repos/products.py` | source | Product records keyed by id; lookup by SKU. | - |
| `shipdesk/repos/returns.py` | source | Return records keyed by id; lookup by order. | - |
| `shipdesk/repos/shipments.py` | source | Shipment records keyed by id; lookup by order. | - |
| `shipdesk/search/` | source | Package for product search | - |
| `shipdesk/search/__init__.py` | source | Package for product search. | - |
| `shipdesk/search/index.py` | source | Keyword index over product names and SKUs; ranks by matching tokens. | - |
| `shipdesk/services/` | source | Package of business services | - |
| `shipdesk/services/__init__.py` | source | Package of business services. | - |
| `shipdesk/services/fraud_service.py` | source | Risk score from order size, customer age, and country mismatch; maps score to an action. | - |
| `shipdesk/services/gift_cards.py` | source | Gift card redeem (may reach exactly zero) and top-up with a cap. | - |
| `shipdesk/services/inventory_service.py` | source | Stock reservation and release on plain dicts; low-stock list is strictly below the threshold. | - |
| `shipdesk/services/promotions.py` | source | Free-shipping progress banner text; display only, separate from the checkout rule. | - |
| `shipdesk/services/returns_service.py` | source | Return eligibility (window inclusive) and refund after the restocking fee. | - |
| `shipdesk/services/subscriptions.py` | source | Subscription ship-date arithmetic; due on the ship date itself. | - |
| `shipdesk/shipping.py` | source | Shipping zones, base rates, weight surcharge, and the free-shipping rule. | NI-102 |
| `shipdesk/storage.py` | source | One JSON file per order in the data directory. | - |
| `shipdesk/tax.py` | source | Sales tax by region on the discounted subtotal. | NI-102 |
| `shipdesk/taxes/` | source | Package of jurisdiction tax tables | - |
| `shipdesk/taxes/__init__.py` | source | Package of jurisdiction tax tables. | - |
| `shipdesk/taxes/us_states.py` | source | US state sales-tax table (50 states) and helpers. | - |
| `shipdesk/taxes/vat.py` | source | EU VAT rate table (27 states) with standard and reduced categories. | - |
| `shipdesk/tiers/` | source | Package of threshold tables; each documents its own inclusive or strict rule | - |
| `shipdesk/tiers/__init__.py` | source | Package of threshold tables; each documents its own inclusive or strict rule. | - |
| `shipdesk/tiers/delivery_speed.py` | source | Delivery surcharge by promised days; fee in cents (negative is a discount). | NI-103 |
| `shipdesk/tiers/fraud_bands.py` | source | Fraud action by risk score; a score at the threshold triggers the band. | NI-103 |
| `shipdesk/tiers/gift_wrap.py` | source | Per-item gift wrap price by item count; multi means MORE than 3 items (strict). | NI-103 |
| `shipdesk/tiers/handling_fee.py` | source | Handling surcharge by parcel weight; heavy means MORE than 20 kg (strict). | NI-103 |
| `shipdesk/tiers/insurance.py` | source | Insurance premium by declared value in cents. | NI-103 |
| `shipdesk/tiers/loyalty.py` | source | Loyalty tier by lifetime points; benefit is a discount in basis points. | NI-103 |
| `shipdesk/tiers/restocking_fee.py` | source | Restocking fee in basis points by days since delivery; partial means MORE than 14 days (strict). | NI-103 |
| `shipdesk/tiers/return_window.py` | source | Return window in days by customer tenure; valued means MORE than 365 days (strict). | NI-103 |
| `shipdesk/tiers/sla_priority.py` | source | Support priority by ticket age in hours; p2 means MORE than 24 hours (strict). | NI-103 |
| `shipdesk/tiers/volume_pricing.py` | source | Wholesale discount in basis points by units per order. | NI-103 |
| `shipdesk/validators.py` | source | Address and coupon-format validation. | - |
| `shipdesk/zones/` | source | Package mapping postal codes to delivery zones | - |
| `shipdesk/zones/__init__.py` | source | Package mapping postal codes to delivery zones. | - |
| `shipdesk/zones/holidays.py` | source | 2026 public holiday calendars for eight countries and business-day helpers. | - |
| `shipdesk/zones/uk_postcode.py` | source | UK postcode-area to delivery-region table. | - |
| `shipdesk/zones/us_zip.py` | source | US ZIP-prefix to delivery-zone table; range ends are inclusive. | - |
| `tests/**` | test | Test suite mirroring the package layout (test_<module>.py), plus data files under tests/data/. | - |
| `tools/` | source | Demo command-line helpers | - |
| `tools/export_orders.py` | source | CLI that exports order records in six formats. | - |
| `tools/seed_orders.py` | source | Demo helper that prints the seed catalog. | - |
