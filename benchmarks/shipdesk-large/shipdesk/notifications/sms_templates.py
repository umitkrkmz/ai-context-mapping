"""SMS templates."""
from .locale_strings import text

MAX_LENGTH = 160


def shipped(order_id: str, language: str = "en") -> str:
    message = f"{text('shipped', language)}: {order_id}. {text('track', language)}"
    return message if len(message) <= MAX_LENGTH else message[: MAX_LENGTH - 3] + "..."
