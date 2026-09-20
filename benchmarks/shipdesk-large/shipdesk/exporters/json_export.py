"""JSON export of order records, sorted by order id."""
import json
from typing import Dict, List

from . import FIELDS


def render(records: List[Dict[str, object]]) -> str:
    rows = [{field: record.get(field) for field in FIELDS} for record in records]
    rows.sort(key=lambda row: str(row["order_id"]))
    return json.dumps(rows, indent=2)
