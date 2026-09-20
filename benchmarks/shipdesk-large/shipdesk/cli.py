"""Command-line entry point: quote a cart described by "SKU:QTY" arguments."""
import argparse
import sys

from .cart import Cart
from .checkout import compute_quote
from .formatting import format_quote
from .models import Address
from .validators import validate_address


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="shipdesk", description="Quote a cart.")
    parser.add_argument("items", nargs="+", help="items as SKU:QTY, for example MUG-01:2")
    parser.add_argument("--country", default="US")
    parser.add_argument("--region", default="CA")
    parser.add_argument("--coupon")
    args = parser.parse_args(argv)
    cart = Cart()
    for spec in args.items:
        sku, _, qty = spec.partition(":")
        cart.add(sku, int(qty or 1))
    address = Address(args.country, args.region)
    validate_address(address)
    print(format_quote(compute_quote(cart, address, args.coupon)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
