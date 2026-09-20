# Handling fee tiers

Rule: **strict**.

Heavy applies to parcels MORE than 20,000 g; a parcel of exactly 20,000 g is standard. Oversize is more than 50,000 g.

Module: `shipdesk/tiers/handling_fee.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_handling_fee.py` pin the boundary behavior described here.
