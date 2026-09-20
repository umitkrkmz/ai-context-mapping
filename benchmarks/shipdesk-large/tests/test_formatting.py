from shipdesk.formatting import format_quote
from shipdesk.models import Quote


def test_format_quote_lines():
    text = format_quote(Quote(5000, 500, 0, 326, 4826))
    lines = text.splitlines()
    assert lines[0].startswith("Subtotal") and lines[0].endswith("50.00")
    assert lines[1].endswith("-5.00")
    assert lines[-1].startswith("Total") and lines[-1].endswith("48.26")
