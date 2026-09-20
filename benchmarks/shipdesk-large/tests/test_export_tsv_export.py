from shipdesk.exporters import tsv_export as m


def test_render_basic():
    assert m.render([{"order_id": "A"}]).splitlines()[1].startswith("A\t")


def test_render_empty_has_header_or_wrapper():
    assert m.render([]) != ""
