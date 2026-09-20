# Onboarding

1. Read `docs/architecture.md` for the layers and `docs/adr/` for the decisions behind them.
2. Run the tests: `python -m pytest -q`.
3. Quote a cart: `python -m shipdesk.cli MUG-01:2 --country US --region CA`.
4. Business rules live in `docs/pricing-policy.md`; tier tables in `docs/tiers.md`.
5. Data files go in `SHIPDESK_DATA_DIR` (default `./data`).

Conventions: integer cents, one JSON file per entity kind, small pure functions, tests mirror the package layout.
