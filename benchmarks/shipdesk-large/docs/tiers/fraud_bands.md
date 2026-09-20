# Fraud bands tiers

Rule: **inclusive**.

Review from score 40, hold from 70, block from 90. A score of exactly 90 blocks.

Module: `shipdesk/tiers/fraud_bands.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_fraud_bands.py` pin the boundary behavior described here.
