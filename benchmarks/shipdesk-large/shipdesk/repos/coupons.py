"""Coupon repository."""
from typing import Any, Dict, Optional

from .base import JsonRepo


class CouponRepo(JsonRepo):
    kind = "coupons"

    def find_by_code(self, value: str) -> Optional[Dict[str, Any]]:
        needle = value.lower()
        for record in self.all():
            if str(record.get("code", "")).lower() == needle:
                return record
        return None


REPO = CouponRepo()
