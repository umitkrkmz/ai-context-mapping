"""Currency metadata, display formatting, and fixed reference conversion (rates are illustrative)."""
from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class Currency:
    code: str
    symbol: str
    decimals: int
    name: str
    rate_x100: int  # major units of this currency per 1 USD, times 100 (EUR 92 means 0.92)


CURRENCIES: Dict[str, Currency] = {
    "USD": Currency("USD", "$", 2, "US Dollar", 100),
    "EUR": Currency("EUR", "EUR ", 2, "Euro", 92),
    "GBP": Currency("GBP", "GBP ", 2, "Pound Sterling", 79),
    "JPY": Currency("JPY", "JPY ", 0, "Japanese Yen", 15700),
    "CAD": Currency("CAD", "C$", 2, "Canadian Dollar", 135),
    "AUD": Currency("AUD", "A$", 2, "Australian Dollar", 152),
    "CHF": Currency("CHF", "CHF ", 2, "Swiss Franc", 88),
    "SEK": Currency("SEK", "SEK ", 2, "Swedish Krona", 1050),
    "NOK": Currency("NOK", "NOK ", 2, "Norwegian Krone", 1070),
    "DKK": Currency("DKK", "DKK ", 2, "Danish Krone", 687),
    "PLN": Currency("PLN", "PLN ", 2, "Polish Zloty", 397),
    "CZK": Currency("CZK", "CZK ", 2, "Czech Koruna", 2320),
    "HUF": Currency("HUF", "HUF ", 0, "Hungarian Forint", 36200),
    "BRL": Currency("BRL", "R$", 2, "Brazilian Real", 497),
    "MXN": Currency("MXN", "MX$", 2, "Mexican Peso", 1710),
    "INR": Currency("INR", "INR ", 2, "Indian Rupee", 8330),
    "KRW": Currency("KRW", "KRW ", 0, "South Korean Won", 133000),
    "SGD": Currency("SGD", "S$", 2, "Singapore Dollar", 134),
    "NZD": Currency("NZD", "NZ$", 2, "New Zealand Dollar", 163),
    "ZAR": Currency("ZAR", "ZAR ", 2, "South African Rand", 1830),
    "TRY": Currency("TRY", "TRY ", 2, "Turkish Lira", 3220),
    "AED": Currency("AED", "AED ", 2, "UAE Dirham", 367),
    "SAR": Currency("SAR", "SAR ", 2, "Saudi Riyal", 375),
    "ILS": Currency("ILS", "ILS ", 2, "Israeli Shekel", 365),
}


def format_amount(minor_units: int, code: str) -> str:
    """Format minor units (cents for most currencies) with the currency symbol."""
    currency = CURRENCIES[code]
    sign = "-" if minor_units < 0 else ""
    value = abs(minor_units)
    if currency.decimals == 0:
        return f"{sign}{currency.symbol}{value:,}"
    whole, fraction = divmod(value, 10 ** currency.decimals)
    return f"{sign}{currency.symbol}{whole:,}.{fraction:0{currency.decimals}d}"


def convert(minor_units: int, source: str, target: str) -> int:
    """Convert between currencies through USD cents using the fixed reference rates (half up)."""
    src, dst = CURRENCIES[source], CURRENCIES[target]
    divisor = src.rate_x100 * 10 ** src.decimals
    usd_cents = (2 * minor_units * 10000 + divisor) // (2 * divisor)
    return (2 * usd_cents * dst.rate_x100 * 10 ** dst.decimals + 10000) // 20000
