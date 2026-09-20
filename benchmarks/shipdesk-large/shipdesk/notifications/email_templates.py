"""Email templates."""
from ..money import to_display
from .locale_strings import text


def order_confirmation(order_id: str, total_cents: int, free_shipping: bool, language: str = "en") -> str:
    lines = [f"{text('thanks', language)} {order_id}", f"{text('total', language)}: {to_display(total_cents)}"]
    if free_shipping:
        lines.append(text("free_shipping", language))
    return "\n".join(lines)
