"""Accounting field mapping: translate internal records to the external system's field names."""
from typing import Any, Dict

MAPPING: Dict[str, str] = {
    "order_id": "Reference",
    "total_cents": "Gross",
    "tax_cents": "TaxAmount",
    "shipping_cents": "ShippingIncome",
    "date": "PostingDate",
}
REQUIRED = frozenset({"order_id"})


def to_external(record: Dict[str, Any]) -> Dict[str, Any]:
    """Map known fields; unknown fields are dropped; a missing required field raises KeyError."""
    for field in REQUIRED:
        if field not in record:
            raise KeyError(field)
    return {external: record[internal] for internal, external in MAPPING.items() if internal in record}


def to_internal(payload: Dict[str, Any]) -> Dict[str, Any]:
    reverse = {external: internal for internal, external in MAPPING.items()}
    return {reverse[key]: value for key, value in payload.items() if key in reverse}
