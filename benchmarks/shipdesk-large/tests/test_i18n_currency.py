from shipdesk.i18n.currency import CURRENCIES, convert, format_amount


def test_table_size():
    assert len(CURRENCIES) == 24


def test_format_two_decimals_and_zero_decimals():
    assert format_amount(123456, "USD") == "$1,234.56"
    assert format_amount(-5, "USD") == "-$0.05"
    assert format_amount(1500, "JPY") == "JPY 1,500"


def test_convert_identity_and_direction():
    assert convert(10000, "USD", "USD") == 10000
    assert convert(10000, "USD", "EUR") == 9200
    assert convert(10000, "USD", "JPY") == 15700
    assert convert(convert(10000, "USD", "GBP"), "GBP", "USD") == 10000
