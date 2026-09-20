# FAQ

**Why are some thresholds "more than" and others "at or above"?** Each business owner specified their own. See `docs/tiers.md`.

**Why is there a deprecated shipping module?** The old CSV importer still imports it; see ADR 0005.

**Where do I change the free-shipping threshold?** `FREE_SHIPPING_MIN_CENTS` in `shipdesk/config.py`; the rule that uses it is described in `docs/pricing-policy.md`.

**Can I use floats for money?** No; see ADR 0001.
