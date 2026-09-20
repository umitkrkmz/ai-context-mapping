"""XML export of order records with escaped values."""
from typing import Dict, List
from xml.sax.saxutils import escape

from . import FIELDS


def render(records: List[Dict[str, object]]) -> str:
    parts = ["<orders>"]
    for record in records:
        parts.append("  <order>")
        for field in FIELDS:
            parts.append(f"    <{field}>{escape(str(record.get(field, '')))}</{field}>")
        parts.append("  </order>")
    parts.append("</orders>")
    return "\n".join(parts)
