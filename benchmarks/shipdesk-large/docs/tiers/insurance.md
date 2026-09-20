# Insurance tiers

Rule: **inclusive**.

Basic from 100.00 declared value, plus from 500.00, premium from 2,000.00. Exactly at a threshold takes the higher tier.

Module: `shipdesk/tiers/insurance.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_insurance.py` pin the boundary behavior described here.
