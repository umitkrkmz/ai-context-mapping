from shipdesk.exporters import xml_export as m


def test_render_basic():
    assert "&amp;" in m.render([{"order_id": "A&B"}])


def test_render_empty_has_header_or_wrapper():
    assert m.render([]) != ""
