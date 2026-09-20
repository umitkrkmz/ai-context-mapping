from shipdesk.audit.log import format_entry, parse_entry
from shipdesk.audit.retention import expired, is_expired


def test_format_and_parse_round_trip():
    line = format_entry("2026-01-01T00:00:00", "alice", "refund", {"order": "A1", "cents": 250})
    assert line == "2026-01-01T00:00:00 alice refund cents=250 order=A1"
    parsed = parse_entry(line)
    assert parsed["action"] == "refund" and parsed["details"] == {"cents": "250", "order": "A1"}


def test_retention_is_strict():
    assert not is_expired("sessions", 30)
    assert is_expired("sessions", 31)


def test_expired_filters_records():
    rows = [{"age_days": 7}, {"age_days": 8}]
    assert expired(rows, "exports") == [{"age_days": 8}]
