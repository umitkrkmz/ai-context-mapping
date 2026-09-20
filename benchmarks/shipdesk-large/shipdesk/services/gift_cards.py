"""Gift card balances in integer cents."""


class InsufficientBalance(ValueError):
    pass


def redeem(balance_cents: int, amount_cents: int) -> int:
    """Return the new balance; a card may be drained to exactly zero."""
    if amount_cents < 0:
        raise ValueError("amount must not be negative")
    if amount_cents > balance_cents:
        raise InsufficientBalance(f"balance {balance_cents} is below {amount_cents}")
    return balance_cents - amount_cents


def top_up(balance_cents: int, amount_cents: int, cap_cents: int = 50000) -> int:
    return min(balance_cents + amount_cents, cap_cents)
