# Changelog

## 1.5.0
- Added carrier adapters and the carrier registry.
- Added tier tables: loyalty, handling fee, insurance, gift wrap, volume pricing, return window, fraud bands, SLA priority, delivery speed, restocking fee.
- Added exporters, region helpers, notification templates, repositories, analytics, and services.
- Promotion banners now show free-shipping progress (display only).

## 1.4.2
- Moved the free-shipping check out of `checkout.py` into `shipping.qualifies_for_free_shipping`.
- Added `reports.daily_summary`.

## 1.4.1
- Coupon codes are now case-insensitive.

## 1.4.0
- Added regional shipping zones.
- Deprecated `legacy_shipping`; the old importer still uses it.
