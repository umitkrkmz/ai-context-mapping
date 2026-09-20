from shipdesk.analytics.regions_report import sales_by_region, top_region


def test_sales_by_region_groups():
    rows = [{"country": "US", "region": "CA", "total_cents": 100}, {"country": "US", "region": "CA", "total_cents": 50}]
    assert sales_by_region(rows) == {("US", "CA"): 150}


def test_top_region_and_empty():
    rows = [{"country": "US", "region": "CA", "total_cents": 1}, {"country": "DE", "region": "", "total_cents": 9}]
    assert top_region(rows) == ("DE", "")
    assert top_region([]) is None
