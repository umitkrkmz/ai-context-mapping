# ADR: compute_quote is the only pricing entry point

Status: accepted

Callers must not recombine discount, shipping, and tax themselves; ordering matters (discount, then shipping on the discounted subtotal, then tax on the discounted subtotal).
