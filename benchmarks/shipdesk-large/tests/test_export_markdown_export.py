from shipdesk.exporters import markdown_export as m


def test_render_basic():
    assert m.render([{"order_id": "a|b"}]).splitlines()[2].startswith("| a/b |")


def test_render_empty_has_header_or_wrapper():
    assert m.render([]) != ""
