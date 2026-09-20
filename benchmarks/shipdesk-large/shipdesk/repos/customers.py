"""Customer repository."""
from typing import Any, Dict, Optional

from .base import JsonRepo


class CustomerRepo(JsonRepo):
    kind = "customers"

    def find_by_email(self, value: str) -> Optional[Dict[str, Any]]:
        needle = value.lower()
        for record in self.all():
            if str(record.get("email", "")).lower() == needle:
                return record
        return None


REPO = CustomerRepo()
