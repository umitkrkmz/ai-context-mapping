import pytest

from shipdesk.models import Address
from shipdesk.validators import validate_address, validate_coupon_format


def test_coupon_format():
    assert validate_coupon_format("SPRING5")
    assert not validate_coupon_format("no")
    assert not validate_coupon_format("")


def test_address_rules():
    validate_address(Address("DE"))
    with pytest.raises(ValueError):
        validate_address(Address("USA"))
    with pytest.raises(ValueError):
        validate_address(Address("US"))
