"""Scoring check for the tier-refactoring benchmark (experiment 6). Benchmark agents never see this file.

It compares a refactored ShipDesk copy with the pristine fixture at every tier boundary: for each of the ten
tables in ``shipdesk/tiers/`` and for ``shipdesk/audit/retention.py`` it probes each threshold, one below
and one above, and requires identical results. The project's own tests are not trusted here, because an
agent can edit them. Point it at a project with BENCH_PROJECT:

    BENCH_PROJECT=/path/to/refactored-copy python -m pytest benchmarks/tier_semantics_check.py -q

The file name deliberately does not match ``test_*.py`` so a plain ``pytest`` run does not collect it.
"""
from __future__ import annotations

import importlib
import importlib.util
import os
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, List

import pytest

PRISTINE = Path(__file__).resolve().parent / "shipdesk-large"
TABLES = (
    "delivery_speed", "fraud_bands", "gift_wrap", "handling_fee", "insurance",
    "loyalty", "restocking_fee", "return_window", "sla_priority", "volume_pricing",
)


def load_file(path: Path, name: str) -> ModuleType:
    """Import one source file under a private name (the pristine tier modules import only the standard library)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module  # dataclasses resolves annotations through sys.modules
    spec.loader.exec_module(module)
    return module


def reference_table(table: str) -> ModuleType:
    return load_file(PRISTINE / "shipdesk" / "tiers" / f"{table}.py", f"_pristine_tier_{table}")


def reference_retention() -> ModuleType:
    return load_file(PRISTINE / "shipdesk" / "audit" / "retention.py", "_pristine_retention")


def probe_values(reference: ModuleType) -> List[int]:
    values = {0}
    for tier in reference.TIERS:
        values.update(v for v in (tier.threshold - 1, tier.threshold, tier.threshold + 1) if v >= 0)
    return sorted(values)


def _tier_view(tier: Any) -> Any:
    return None if tier is None else (tier.label, tier.threshold, tier.benefit)


def table_behavior(module: ModuleType, values: List[int]) -> Dict[str, Any]:
    """Everything a caller can observe from a tier table at the given values."""
    out: Dict[str, Any] = {"TIERS": [_tier_view(t) for t in module.TIERS]}
    for value in values:
        out[f"tier_for({value})"] = _tier_view(module.tier_for(value))
        out[f"benefit_for({value})"] = module.benefit_for(value)
        out[f"next_tier({value})"] = _tier_view(module.next_tier(value))
        out[f"distance_to_next({value})"] = module.distance_to_next(value)
        out[f"describe({value})"] = module.describe(value)
    out["summarize"] = dict(module.summarize(values))
    return out


def retention_behavior(module: ModuleType) -> Dict[str, Any]:
    out: Dict[str, Any] = {"RETENTION_DAYS": dict(module.RETENTION_DAYS)}
    for category, days in module.RETENTION_DAYS.items():
        for age in (days - 1, days, days + 1):
            out[f"is_expired({category}, {age})"] = module.is_expired(category, age)
        records = [{"age_days": age} for age in (days - 1, days, days + 1)]
        out[f"expired({category})"] = [r["age_days"] for r in module.expired(records, category)]
    return out


def differences(expected: Dict[str, Any], observed_module: ModuleType, behavior, *args: Any) -> List[str]:
    """Probes whose result differs from the reference; a missing name or a crash is a difference too."""
    try:
        observed = behavior(observed_module, *args)
    except Exception as exc:  # noqa: BLE001 - any failure to answer a probe is a behavior change
        return [f"probe failed: {type(exc).__name__}: {exc}"]
    return [f"{key}: expected {expected[key]!r}, got {observed.get(key)!r}" for key in expected if observed.get(key) != expected[key]]


def _project_module(dotted: str) -> ModuleType:
    project = os.environ.get("BENCH_PROJECT")
    if not project:
        pytest.skip("BENCH_PROJECT is not set")
    if project not in sys.path:
        sys.path.insert(0, project)
    return importlib.import_module(dotted)


@pytest.mark.parametrize("table", TABLES)
def test_tier_table_behavior_is_unchanged(table: str) -> None:
    reference = reference_table(table)
    values = probe_values(reference)
    expected = table_behavior(reference, values)
    assert differences(expected, _project_module(f"shipdesk.tiers.{table}"), table_behavior, values) == []


def test_retention_behavior_is_unchanged() -> None:
    expected = retention_behavior(reference_retention())
    assert differences(expected, _project_module("shipdesk.audit.retention"), retention_behavior) == []
