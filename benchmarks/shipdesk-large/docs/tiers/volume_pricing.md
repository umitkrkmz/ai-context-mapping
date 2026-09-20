# Volume pricing tiers

Rule: **inclusive**.

Tier 1 from 25 units, tier 2 from 100, tier 3 from 500. Ordering exactly 100 units earns tier 2.

Module: `shipdesk/tiers/volume_pricing.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_volume_pricing.py` pin the boundary behavior described here.
