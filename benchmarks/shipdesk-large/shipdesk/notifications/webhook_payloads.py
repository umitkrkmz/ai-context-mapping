"""Webhook templates."""
import json


def order_event(event: str, order_id: str, total_cents: int) -> str:
    """Stable JSON payload for partner webhooks: keys are sorted so signatures stay reproducible."""
    return json.dumps({"event": event, "order_id": order_id, "total_cents": total_cents}, sort_keys=True)
