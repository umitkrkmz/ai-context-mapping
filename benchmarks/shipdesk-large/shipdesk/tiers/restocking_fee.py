"""Restocking fee: Restocking fee in basis points by days since delivery; partial means MORE than 14 days (strict).

Rule: a value strictly exceeds the tier threshold to reach that tier (strict: more than).
The exact semantics of every tier table are recorded in docs/tiers.md; do not change a
comparison operator to "match" another table.
"""
from dataclasses import dataclass
from typing import Dict, Iterable, List, Optional

UNIT = "days"


@dataclass(frozen=True)
class Tier:
    label: str
    threshold: int
    benefit: int


TIERS: List[Tier] = [
    Tier("none", 0, 0),
    Tier("partial", 14, 1000),
    Tier("full", 30, 2500),
]


def tier_for(value: int) -> Tier:
    """Return the highest tier reached by ``value`` (strict: more than)."""
    reached = TIERS[0]
    for tier in TIERS[1:]:
        if value > tier.threshold:
            reached = tier
    return reached


def benefit_for(value: int) -> int:
    return tier_for(value).benefit


def next_tier(value: int) -> Optional[Tier]:
    """Return the next tier above the one ``value`` has reached, or None at the top."""
    current = tier_for(value)
    index = TIERS.index(current)
    return TIERS[index + 1] if index + 1 < len(TIERS) else None


def distance_to_next(value: int) -> Optional[int]:
    """Return how many more days are needed to reach the next tier."""
    upcoming = next_tier(value)
    if upcoming is None:
        return None
    return upcoming.threshold - value + 1


def summarize(values: Iterable[int]) -> Dict[str, int]:
    """Count how many values fall in each tier."""
    counts = {tier.label: 0 for tier in TIERS}
    for value in values:
        counts[tier_for(value).label] += 1
    return counts


def describe(value: int) -> str:
    tier = tier_for(value)
    return f"{value} {UNIT} -> {tier.label} (benefit {tier.benefit})"
