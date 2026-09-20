import json

from shipdesk.exporters import json_export as m


def test_render_basic():
    assert json.loads(m.render([{"order_id": "B"}, {"order_id": "A"}]))[0]["order_id"] == "A"


def test_render_empty_has_header_or_wrapper():
    assert m.render([]) != ""
