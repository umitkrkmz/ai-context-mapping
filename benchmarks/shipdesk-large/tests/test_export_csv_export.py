from shipdesk.exporters import csv_export as m


def test_render_basic():
    assert m.render([{"order_id": "A", "country": "US", "region": "CA", "total_cents": 1, "shipping_cents": 0}]).splitlines()[1] == "A,US,CA,1,0"


def test_render_empty_has_header_or_wrapper():
    assert m.render([]) != ""
