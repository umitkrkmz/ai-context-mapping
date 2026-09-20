"""Markdown table export of order records; pipes in values are escaped."""
from typing import Dict, List

from . import FIELDS


def render(records: List[Dict[str, object]]) -> str:
    lines = ["| " + " | ".join(FIELDS) + " |", "| " + " | ".join("---" for _ in FIELDS) + " |"]
    for record in records:
        cells = [str(record.get(field, "")).replace("|", "/") for field in FIELDS]
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
