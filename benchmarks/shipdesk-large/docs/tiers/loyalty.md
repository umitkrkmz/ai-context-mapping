# Loyalty tiers

Rule: **inclusive**.

Silver starts at 500 points, gold at 1000, platinum at 5000. A customer with exactly 1000 points is gold. Benefits are basis points of discount.

Module: `shipdesk/tiers/loyalty.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_loyalty.py` pin the boundary behavior described here.
