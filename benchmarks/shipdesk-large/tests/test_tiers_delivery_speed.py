from shipdesk.tiers import delivery_speed as m


def test_zero_is_lowest_tier():
    assert m.tier_for(0).label == m.TIERS[0].label


def test_thresholds_follow_documented_semantics():
    for tier in m.TIERS[1:]:
        edge = tier.threshold
        assert m.tier_for(edge).label == tier.label
        assert m.tier_for(edge - 1).label != tier.label


def test_benefit_matches_tier():
    for tier in m.TIERS:
        probe = tier.threshold
        assert m.benefit_for(probe) == tier.benefit


def test_next_tier_and_distance():
    first, second = m.TIERS[0], m.TIERS[1]
    assert m.next_tier(0) is second
    assert m.distance_to_next(0) == second.threshold
    assert m.next_tier(m.TIERS[-1].threshold) is None
    assert m.distance_to_next(m.TIERS[-1].threshold) is None
    assert first.label == m.TIERS[0].label


def test_summarize_counts_every_value():
    values = [0, m.TIERS[1].threshold, m.TIERS[-1].threshold]
    counts = m.summarize(values)
    assert sum(counts.values()) == 3
    assert counts[m.TIERS[-1].label] == 1


def test_describe_mentions_label():
    assert m.tier_for(0).label in m.describe(0)
