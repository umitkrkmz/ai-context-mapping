"""Scoring check for the free-shipping benchmark. Benchmark agents never see this file.

It verifies that a fixed ShipDesk copy treats a subtotal of exactly 50.00 as free shipping while
leaving every neighboring behavior unchanged. Point it at a project with BENCH_PROJECT:

    BENCH_PROJECT=/path/to/shipdesk-copy python -m pytest benchmarks/acceptance_check.py -q

The file name deliberately does not match ``test_*.py`` so a plain ``pytest`` run from the
repository root does not collect it (it fails on the unfixed fixture by design).
"""
import os
import sys

PROJECT = os.environ.get("BENCH_PROJECT") or os.path.join(os.path.dirname(os.path.abspath(__file__)), "shipdesk")
sys.path.insert(0, PROJECT)

from shipdesk.cart import Cart  # noqa: E402
from shipdesk.checkout import compute_quote  # noqa: E402
from shipdesk.models import Address  # noqa: E402
from shipdesk.money import to_cents  # noqa: E402
from shipdesk.shipping import qualifies_for_free_shipping, shipping_cost_cents  # noqa: E402


def test_exact_threshold_ships_free():
    assert qualifies_for_free_shipping(5000)


def test_one_cent_below_threshold_pays():
    assert not qualifies_for_free_shipping(4999)


def test_one_cent_above_threshold_ships_free():
    assert qualifies_for_free_shipping(5001)


def test_zero_pays():
    assert not qualifies_for_free_shipping(0)


def test_checkout_with_exactly_fifty_ships_free():
    cart = Cart()
    cart.add("TEE-02", 2)
    quote = compute_quote(cart, Address("US", "OR"))
    assert quote.subtotal_cents == 5000
    assert quote.shipping_cents == 0
    assert quote.total_cents == 5000


def test_checkout_just_below_fifty_pays_base_rate():
    cart = Cart()
    cart.add("TEE-02", 1)
    cart.add("BAG-03", 1)
    cart.add("PEN-05", 2)
    quote = compute_quote(cart, Address("US", "OR"))
    assert quote.subtotal_cents == 4900
    assert quote.shipping_cents == 599


def test_shipping_rates_unchanged_below_threshold():
    assert shipping_cost_cents(4999, 500, Address("DE")) == 1999
    assert shipping_cost_cents(4999, 2500, Address("US", "CA")) == 599 + 300


def test_money_rounding_invariant_intact():
    assert to_cents("0.285") == 29
