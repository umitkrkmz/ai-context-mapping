"""Order risk scoring."""
from ..tiers import fraud_bands

ACTIONS = {0: "accept", 1: "review", 2: "hold", 3: "block"}


def risk_score(order_cents: int, new_customer: bool, country_mismatch: bool) -> int:
    score = min(order_cents // 1000, 40)
    score += 25 if new_customer else 0
    score += 30 if country_mismatch else 0
    return min(score, 100)


def action_for(order_cents: int, new_customer: bool, country_mismatch: bool) -> str:
    return ACTIONS[fraud_bands.benefit_for(risk_score(order_cents, new_customer, country_mismatch))]
