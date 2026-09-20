# ADR: Display helpers never decide

Status: accepted

Promotion banners and reports may compute their own thresholds for display, but eligibility decisions live in `shipping.py`.
