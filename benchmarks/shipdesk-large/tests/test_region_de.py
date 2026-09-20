from shipdesk.regions import de as m


def test_valid_and_invalid_postal():
    assert m.is_valid_postal("10115")
    assert not m.is_valid_postal("1011")


def test_normalize_postal_strips_and_uppercases():
    assert m.normalize_postal("  10115  ") == m.normalize_postal("10115")


def test_phone_drops_trunk_zero():
    assert m.format_phone("0 555 0100") == m.DIAL_CODE + " 5550100"


def test_address_layout_contains_parts():
    text = m.format_address("Ada", "1 Main St", "Town", "ST", "10115")
    assert "Ada" in text and "1 Main St" in text
