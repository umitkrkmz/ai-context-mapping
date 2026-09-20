import json
from collections import Counter
from pathlib import Path

from shipdesk.integrations import crm_sync
from shipdesk.tiers import loyalty

CUSTOMERS = json.loads((Path(__file__).parent / "data" / "sample_customers.json").read_text(encoding="utf-8"))


def test_sample_customers_load():
    assert len(CUSTOMERS) == 120
    assert len({c["email"] for c in CUSTOMERS}) == 120


def test_loyalty_summary_covers_everyone():
    counts = loyalty.summarize(c["loyalty_points"] for c in CUSTOMERS)
    assert sum(counts.values()) == 120
    assert counts["platinum"] > 0


def test_crm_mapping_round_trip():
    record = {"email": CUSTOMERS[0]["email"], "name": CUSTOMERS[0]["name"], "country": CUSTOMERS[0]["country"]}
    assert crm_sync.to_internal(crm_sync.to_external(record)) == record


def test_country_mix():
    assert set(Counter(c["country"] for c in CUSTOMERS)) == {"US", "CA", "GB", "DE", "FR", "JP", "AU"}
