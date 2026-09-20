import json
from pathlib import Path

from shipdesk.services.returns_service import refund_cents, within_window

RETURNS = json.loads((Path(__file__).parent / "data" / "sample_returns.json").read_text(encoding="utf-8"))


def test_sample_returns_load():
    assert len(RETURNS) == 140
    assert len({r["return_id"] for r in RETURNS}) == 140


def test_refunds_never_exceed_payment_and_never_go_negative():
    for row in RETURNS:
        refund = refund_cents(row["paid_cents"], row["days_since_delivery"])
        assert 0 <= refund <= row["paid_cents"]


def test_window_rule_over_the_sample():
    allowed = [r for r in RETURNS if within_window(r["tenure_days"], r["days_since_delivery"])]
    assert 0 < len(allowed) < len(RETURNS)
