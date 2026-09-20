# ADR: Money is integer cents

Status: accepted

Floats cannot represent 0.10 exactly, and totals must reconcile to the cent. Every amount is an int of minor units; rates are basis points; rounding is half up via `money.apply_bps`.
