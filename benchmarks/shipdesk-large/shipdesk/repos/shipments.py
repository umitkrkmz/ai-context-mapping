"""Shipment repository."""
from typing import Any, Dict, Optional

from .base import JsonRepo


class ShipmentRepo(JsonRepo):
    kind = "shipments"

    def find_by_order(self, value: str) -> Optional[Dict[str, Any]]:
        needle = value.lower()
        for record in self.all():
            if str(record.get("order_id", "")).lower() == needle:
                return record
        return None


REPO = ShipmentRepo()
