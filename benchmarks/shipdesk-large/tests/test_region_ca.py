from shipdesk.regions import ca as m


def test_valid_and_invalid_postal():
    assert m.is_valid_postal("K1A 0B1")
    assert not m.is_valid_postal("K1A0B")


def test_normalize_postal_strips_and_uppercases():
    assert m.normalize_postal("  K1A 0B1  ") == m.normalize_postal("K1A 0B1")


def test_phone_drops_trunk_zero():
    assert m.format_phone("0 555 0100") == m.DIAL_CODE + " 5550100"


def test_address_layout_contains_parts():
    text = m.format_address("Ada", "1 Main St", "Town", "ST", "K1A 0B1")
    assert "Ada" in text and "1 Main St" in text
