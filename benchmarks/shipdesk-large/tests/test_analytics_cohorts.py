from shipdesk.analytics.cohorts import cohorts


def test_cohorts_group_by_month():
    rows = [{"date": "2026-02-10", "customer": "b"}, {"date": "2026-02-01", "customer": "a"}, {"date": "2026-01-31", "customer": "c"}]
    assert cohorts(rows) == {"2026-01": ["c"], "2026-02": ["a", "b"]}
