"""Human-readable quote formatting."""
from .models import Quote
from .money import to_display


def format_quote(quote: Quote) -> str:
    rows = [
        ("Subtotal", quote.subtotal_cents),
        ("Discount", -quote.discount_cents),
        ("Shipping", quote.shipping_cents),
        ("Tax", quote.tax_cents),
        ("Total", quote.total_cents),
    ]
    return "\n".join(f"{label:<10}{to_display(cents):>10}" for label, cents in rows)
