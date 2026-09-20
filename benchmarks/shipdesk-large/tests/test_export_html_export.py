from shipdesk.exporters import html_export as m


def test_render_basic():
    assert "&lt;b&gt;" in m.render([{"order_id": "<b>"}])


def test_render_empty_has_header_or_wrapper():
    assert m.render([]) != ""
