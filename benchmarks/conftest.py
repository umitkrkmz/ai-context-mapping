"""Keep pytest out of the benchmark fixtures.

The ShipDesk fixtures contain a planted bug and their own test suites, and several test modules share
names across the small and large fixtures. Collecting them from the repository root would fail, so
they are skipped here. Copy a fixture elsewhere (see docs/benchmark-results.md) to run its tests.
"""
collect_ignore = ["shipdesk", "shipdesk-large", "shipdesk-overlay", "shipdesk-large-overlay"]
