"""Push templates."""
from ..money import to_display
from .locale_strings import text


def refund(order_id: str, amount_cents: int, language: str = "en") -> dict:
    return {"title": text("refund", language), "body": f"{order_id}: {to_display(amount_cents)}"}
