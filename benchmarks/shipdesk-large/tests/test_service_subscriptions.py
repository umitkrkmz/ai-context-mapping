from shipdesk.services.subscriptions import is_due, next_ship_date


def test_next_ship_date():
    assert next_ship_date("2026-01-01", "weekly") == "2026-01-08"
    assert next_ship_date("2026-01-30", "monthly") == "2026-03-01"


def test_due_on_and_after_the_date():
    assert is_due("2026-02-01", "2026-02-01")
    assert is_due("2026-02-01", "2026-02-02")
    assert not is_due("2026-02-01", "2026-01-31")
