"""Translated message fragments used by every channel."""
STRINGS = {
    "en": {"thanks": "Thank you for your order", "shipped": "Your order has shipped", "total": "Total",
           "free_shipping": "Shipping is free", "track": "Track your parcel", "refund": "Your refund is on its way"},
    "de": {"thanks": "Vielen Dank fuer Ihre Bestellung", "shipped": "Ihre Bestellung wurde versandt", "total": "Summe",
           "free_shipping": "Versand kostenlos", "track": "Sendung verfolgen", "refund": "Ihre Erstattung ist unterwegs"},
    "fr": {"thanks": "Merci pour votre commande", "shipped": "Votre commande a ete expediee", "total": "Total",
           "free_shipping": "Livraison gratuite", "track": "Suivre votre colis", "refund": "Votre remboursement est en route"},
    "es": {"thanks": "Gracias por su pedido", "shipped": "Su pedido ha sido enviado", "total": "Total",
           "free_shipping": "Envio gratis", "track": "Siga su paquete", "refund": "Su reembolso esta en camino"},
}
DEFAULT_LANGUAGE = "en"


def text(key: str, language: str = DEFAULT_LANGUAGE) -> str:
    """Look up a fragment; unknown languages fall back to English."""
    table = STRINGS.get(language, STRINGS[DEFAULT_LANGUAGE])
    return table.get(key, STRINGS[DEFAULT_LANGUAGE][key])
