import pytest

from shipdesk.integrations.marketplace_feed import MAPPING, to_external, to_internal


def test_round_trip():
    record = {internal: index for index, internal in enumerate(MAPPING)}
    assert to_internal(to_external(record)) == record


def test_unknown_fields_are_dropped():
    assert to_external({"sku": 1, "surprise": 2}) == {"ProductId": 1}


def test_required_field_missing():
    with pytest.raises(KeyError):
        to_external({"surprise": 1})
