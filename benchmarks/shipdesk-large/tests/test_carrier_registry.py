from shipdesk.carriers.registry import REGISTRY, carriers_for, cheapest, get_carrier


def test_lookup_is_case_insensitive():
    assert get_carrier("UPS") is REGISTRY["ups"]


def test_carriers_for_country():
    names = {c.name for c in carriers_for("JP")}
    assert {"FedEx", "DHL", "Yamato"} <= names


def test_cheapest_domestic_us_is_usps():
    assert cheapest(400, "domestic", "US").name == "USPS"


def test_cheapest_none_when_too_heavy():
    assert cheapest(999999, "domestic", "US") is None
