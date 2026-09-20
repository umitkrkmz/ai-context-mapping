from shipdesk.catalog_seed import SEED_ROWS, load_seed


def test_seed_has_unique_skus():
    assert len(SEED_ROWS) == 100
    assert len({row[0] for row in SEED_ROWS}) == 100


def test_load_seed_builds_items():
    items = load_seed()
    assert items["SEED-0001"].name == "Enamel Mug"
    assert all(item.unit_cents > 0 and item.weight_grams > 0 for item in items.values())
