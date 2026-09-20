# SLA priority tiers

Rule: **strict**.

P2 applies to tickets MORE than 24 hours old; a 24-hour-old ticket is still p3.

Module: `shipdesk/tiers/sla_priority.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_sla_priority.py` pin the boundary behavior described here.
