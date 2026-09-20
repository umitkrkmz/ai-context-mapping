from shipdesk.services.promotions import banner_shows_unlocked, banner_text, progress_to_free_shipping


def test_progress():
    assert progress_to_free_shipping(4000) == 1000
    assert progress_to_free_shipping(5000) == 0
    assert progress_to_free_shipping(9000) == 0


def test_banner_text():
    assert banner_text(4000) == "Add 10.00 more for free shipping"
    assert banner_text(5000) == "You have free shipping!"


def test_unlocked_flag():
    assert banner_shows_unlocked(5000)
    assert not banner_shows_unlocked(4999)
