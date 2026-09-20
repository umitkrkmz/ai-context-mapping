from shipdesk.tax import tax_cents


def test_known_region():
    assert tax_cents(10000, "CA") == 725


def test_untaxed_and_unknown_regions():
    assert tax_cents(10000, "OR") == 0
    assert tax_cents(10000, "ZZ") == 0
