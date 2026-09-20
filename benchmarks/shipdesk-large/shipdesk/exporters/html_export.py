"""HTML table export of order records with escaped values."""
from html import escape
from typing import Dict, List

from . import FIELDS


def render(records: List[Dict[str, object]]) -> str:
    head = "".join(f"<th>{escape(field)}</th>" for field in FIELDS)
    body = "".join(
        "<tr>" + "".join(f"<td>{escape(str(record.get(field, '')))}</td>" for field in FIELDS) + "</tr>"
        for record in records
    )
    return f"<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>"
