"""UK postcode areas and the delivery region each belongs to."""
import re
from typing import Optional

AREA_REGIONS = {
    "AB": "Scotland",
    "AL": "East",
    "B": "West Midlands",
    "BA": "South West",
    "BB": "North West",
    "BD": "Yorkshire",
    "BH": "South West",
    "BL": "North West",
    "BN": "South East",
    "BR": "London",
    "BS": "South West",
    "CA": "North West",
    "CB": "East",
    "CF": "Wales",
    "CH": "North West",
    "CM": "East",
    "CO": "East",
    "CR": "London",
    "CT": "South East",
    "CV": "West Midlands",
    "DA": "South East",
    "DD": "Scotland",
    "DE": "East Midlands",
    "DG": "Scotland",
    "DH": "North East",
    "DL": "North East",
    "DN": "Yorkshire",
    "DT": "South West",
    "DY": "West Midlands",
    "E": "London",
    "EC": "London",
    "EH": "Scotland",
    "EN": "London",
    "EX": "South West",
    "FK": "Scotland",
    "FY": "North West",
    "G": "Scotland",
    "GL": "South West",
    "GU": "South East",
    "HA": "London",
    "HD": "Yorkshire",
    "HG": "Yorkshire",
    "HP": "South East",
    "HR": "West Midlands",
    "HS": "Scotland",
    "HU": "Yorkshire",
    "HX": "Yorkshire",
    "IG": "London",
    "IP": "East",
    "IV": "Scotland",
    "KA": "Scotland",
    "KT": "London",
    "KW": "Scotland",
    "KY": "Scotland",
    "L": "North West",
    "LA": "North West",
    "LD": "Wales",
    "LE": "East Midlands",
    "LL": "Wales",
    "LN": "East Midlands",
    "LS": "Yorkshire",
    "LU": "East",
    "M": "North West",
    "ME": "South East",
    "MK": "South East",
    "ML": "Scotland",
    "N": "London",
    "NE": "North East",
    "NG": "East Midlands",
}
_AREA = re.compile(r"^([A-Z]{1,2})\d")


def area_of(postcode: str) -> Optional[str]:
    match = _AREA.match(postcode.strip().upper())
    return match.group(1) if match else None


def region_for_postcode(postcode: str) -> Optional[str]:
    area = area_of(postcode)
    return AREA_REGIONS.get(area) if area else None


def is_highlands_and_islands(postcode: str) -> bool:
    return area_of(postcode) in {"HS", "IV", "KW"}
