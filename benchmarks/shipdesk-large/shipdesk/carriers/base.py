"""Shared carrier behavior: weight-band rate lookup and country support."""
from typing import Dict, FrozenSet, List, Tuple


class WeightLimitExceeded(ValueError):
    """Raised when a parcel is heavier than the carrier's largest weight band."""


class Carrier:
    name = ""
    countries: FrozenSet[str] = frozenset()
    rate_table: Dict[str, List[Tuple[int, int]]] = {}
    transit_days: Dict[str, int] = {}

    def supports(self, country: str) -> bool:
        return country in self.countries

    def estimate_cents(self, weight_grams: int, zone: str) -> int:
        """Price of the first band whose limit is at or above the parcel weight."""
        for limit_grams, cents in self.rate_table[zone]:
            if weight_grams <= limit_grams:
                return cents
        raise WeightLimitExceeded(f"{self.name}: {weight_grams} g exceeds the largest band")

    def transit(self, zone: str) -> int:
        return self.transit_days[zone]

    def label_code(self, service: str) -> str:
        return f"{self.name[:3].upper()}-{service.upper()}"
