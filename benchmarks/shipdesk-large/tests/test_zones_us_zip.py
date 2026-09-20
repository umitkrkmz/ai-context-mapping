from shipdesk.zones.us_zip import ZONE_RANGES, prefix_of, surcharge_cents, zone_for_zip


def test_ranges_are_sorted_and_gap_free():
    assert ZONE_RANGES[0][0] == 0 and ZONE_RANGES[-1][1] == 999
    for (_, last, _), (first, _, _) in zip(ZONE_RANGES, ZONE_RANGES[1:]):
        assert first == last + 1


def test_both_range_ends_are_inclusive():
    first, last, zone = ZONE_RANGES[3]
    assert zone_for_zip(f"{first:03d}00") == zone
    assert zone_for_zip(f"{last:03d}99") == zone


def test_bad_input():
    assert prefix_of("ab") is None
    assert zone_for_zip("") is None


def test_surcharge_starts_at_zone_seven():
    assert surcharge_cents(6) == 0
    assert surcharge_cents(7) == 250
