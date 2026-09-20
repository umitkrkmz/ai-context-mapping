"""Product repository."""
from typing import Any, Dict, Optional

from .base import JsonRepo


class ProductRepo(JsonRepo):
    kind = "products"

    def find_by_sku(self, value: str) -> Optional[Dict[str, Any]]:
        needle = value.lower()
        for record in self.all():
            if str(record.get("sku", "")).lower() == needle:
                return record
        return None


REPO = ProductRepo()
