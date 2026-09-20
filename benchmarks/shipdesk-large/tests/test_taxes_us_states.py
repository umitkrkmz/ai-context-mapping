from shipdesk.taxes.us_states import NO_TAX_STATES, STATE_RATES_BPS, has_sales_tax, state_tax_cents


def test_fifty_states():
    assert len(STATE_RATES_BPS) == 50


def test_no_tax_states():
    assert {"AK", "DE", "MT", "NH", "OR"} == set(NO_TAX_STATES)
    assert not has_sales_tax("OR") and has_sales_tax("CA")


def test_state_tax_cents():
    assert state_tax_cents(10000, "CA") == 725
    assert state_tax_cents(10000, "OR") == 0
