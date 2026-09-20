import json
from pathlib import Path

from shipdesk.analytics.regions_report import top_region
from shipdesk.analytics.revenue import average_order_cents, revenue_by_day
from shipdesk.analytics.shipping_report import free_shipping_share
from shipdesk.exporters import csv_export

ORDERS = json.loads((Path(__file__).parent / "data" / "sample_orders.json").read_text(encoding="utf-8"))


def test_sample_orders_load():
    assert len(ORDERS) == 120


def test_reports_over_sample_orders():
    assert average_order_cents(ORDERS) > 0
    assert sum(revenue_by_day(ORDERS).values()) == sum(o["total_cents"] for o in ORDERS)
    assert 0.0 < free_shipping_share(ORDERS) < 1.0
    assert top_region(ORDERS) is not None


def test_csv_export_of_sample_orders():
    assert len(csv_export.render(ORDERS).splitlines()) == 121
