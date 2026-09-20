"""Tab-separated export of order records."""
from typing import Dict, List

from . import FIELDS


def render(records: List[Dict[str, object]]) -> str:
    lines = ["\t".join(FIELDS)]
    for record in records:
        lines.append("\t".join(str(record.get(field, "")) for field in FIELDS))
    return "\n".join(lines) + "\n"
