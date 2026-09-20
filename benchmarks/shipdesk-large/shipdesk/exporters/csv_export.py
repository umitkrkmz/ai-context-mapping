"""CSV export of order records."""
import csv
import io
from typing import Dict, List

from . import FIELDS


def render(records: List[Dict[str, object]]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow(record)
    return buffer.getvalue()
