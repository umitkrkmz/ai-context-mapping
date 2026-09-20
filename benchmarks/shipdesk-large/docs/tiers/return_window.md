# Return window tiers

Rule: **strict**.

Valued customers are those with MORE than 365 days of tenure; exactly 365 days is still standard.

Module: `shipdesk/tiers/return_window.py`. Business owner sign-off is required to change a threshold or its comparison.
Tests: `tests/test_tiers_return_window.py` pin the boundary behavior described here.
