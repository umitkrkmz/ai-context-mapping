# Runbook

- **Wrong shipping charge:** check `docs/pricing-policy.md`, then `shipdesk/shipping.py`.
- **Order export looks wrong:** exporters read `shipdesk/exporters/__init__.py::FIELDS`.
- **Missing data files:** set `SHIPDESK_DATA_DIR`; the default is `./data`.
- **Deprecated code:** `shipdesk/legacy_shipping.py` is kept for the old importer only.
