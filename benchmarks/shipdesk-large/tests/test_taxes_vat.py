import pytest

from shipdesk.taxes.vat import VAT_RATES, gross_cents, net_from_gross, rate_bps, vat_cents


def test_all_member_states_present():
    assert len(VAT_RATES) == 27


def test_standard_and_reduced_rates():
    assert rate_bps("DE") == 1900
    assert rate_bps("DE", "books") == 700


def test_vat_and_gross():
    assert vat_cents(10000, "DE") == 1900
    assert gross_cents(10000, "FR", "food") == 10550


def test_net_from_gross_round_trip():
    for net in (100, 999, 12345):
        assert net_from_gross(gross_cents(net, "NL"), "NL") == net


def test_unknown_country():
    with pytest.raises(KeyError):
        rate_bps("US")
