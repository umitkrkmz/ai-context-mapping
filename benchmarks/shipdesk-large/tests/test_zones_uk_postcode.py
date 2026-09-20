from shipdesk.zones.uk_postcode import AREA_REGIONS, area_of, is_highlands_and_islands, region_for_postcode


def test_area_extraction():
    assert area_of("sw1a 1aa") is None or area_of("sw1a 1aa") == "SW"
    assert area_of("M1 1AE") == "M"
    assert area_of("EC1A 1BB") == "EC"
    assert area_of("!!") is None


def test_regions():
    assert region_for_postcode("EH1 1YZ") == "Scotland"
    assert region_for_postcode("CF10 1AA") == "Wales"
    assert region_for_postcode("ZZ1 1AA") is None


def test_highlands_and_islands():
    assert is_highlands_and_islands("IV1 1AA")
    assert not is_highlands_and_islands("EH1 1YZ")
    assert len(AREA_REGIONS) > 60
