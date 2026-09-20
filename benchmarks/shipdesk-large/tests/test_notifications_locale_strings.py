from shipdesk.notifications.locale_strings import STRINGS, text


def test_known_language():
    assert text("thanks", "de").startswith("Vielen")


def test_unknown_language_falls_back():
    assert text("thanks", "xx") == STRINGS["en"]["thanks"]


def test_every_language_has_the_same_keys():
    keys = set(STRINGS["en"])
    assert all(set(table) == keys for table in STRINGS.values())
