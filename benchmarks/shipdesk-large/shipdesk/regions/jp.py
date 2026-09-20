"""Japan address helpers: postal code validation, phone numbers, and label layout."""
import re

COUNTRY = "JP"
DIAL_CODE = "+81"
POSTAL = re.compile(r"^\d{3}-?\d{4}$")
LAYOUT = "{postal}\n{region}{city}\n{line1}\n{name}"


def normalize_postal(code: str) -> str:
    """Upper-case a postal code and collapse surrounding whitespace."""
    return " ".join(code.strip().upper().split())


def is_valid_postal(code: str) -> bool:
    return bool(POSTAL.match(normalize_postal(code)))


def format_phone(local_number: str) -> str:
    """Return the number in international form, dropping a leading trunk zero."""
    digits = "".join(ch for ch in local_number if ch.isdigit())
    if digits.startswith("0"):
        digits = digits[1:]
    return f"{DIAL_CODE} {digits}"


def format_address(name: str, line1: str, city: str, region: str, postal: str) -> str:
    return LAYOUT.format(name=name, line1=line1, city=city, region=region, postal=normalize_postal(postal))
