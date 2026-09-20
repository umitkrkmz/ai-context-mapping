# Restocking fee tiers

Rule: **strict**.

Partial fee applies MORE than 14 days after delivery; exactly 14 days is free. Full fee applies after 30.

Module: `shipdesk/tiers/restocking_fee.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_restocking_fee.py` pin the boundary behavior described here.
