"""Tests for the benchmark harness (benchmarks/harness/bench.py) and the tier semantics check.

No test here launches Claude Code or a subprocess: they cover how trial directories are built, the
manipulation check on a transcript's starting context, the schedule, the tree diff, and the scorer's
behavior comparison. Standard library plus pytest only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bench = load(ROOT / "benchmarks" / "harness" / "bench.py", "bench_harness")
semantics = load(ROOT / "benchmarks" / "tier_semantics_check.py", "tier_semantics_check")


# --------------------------------------------------------------------------------------
# Building trial directories
# --------------------------------------------------------------------------------------
@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Dict[str, Path]:
    trials = tmp_path_factory.mktemp("trials")
    return {arm: bench.build("exp6", f"t_{arm}", arm, trials) for arm in ("BD", "BS", "FD", "FS")} | {
        "PG": bench.build("exp5", "t_PG", "PG", trials)}


def test_bare_arm_is_the_untouched_fixture(built: Dict[str, Path]) -> None:
    diff = bench.diff_trees(built["BD"], bench.FIXTURE)
    assert diff == {"added": [], "removed": [], "modified": []}


def test_strip_removes_only_the_guidance(built: Dict[str, Path]) -> None:
    diff = bench.diff_trees(built["BS"], bench.FIXTURE)
    assert diff["added"] == []
    assert diff["removed"] and all(p.startswith(("docs/adr/", "docs/tiers/", "docs/tiers.md")) for p in diff["removed"])
    assert "docs/tiers.md" in diff["removed"] and any(p.startswith("docs/tiers/") for p in diff["removed"])
    docs = ["docs/faq.md", "docs/glossary.md", "docs/onboarding.md"]
    assert sorted(diff["modified"]) == sorted([f"shipdesk/tiers/{t}.py" for t in semantics.TABLES] + docs)
    for table in semantics.TABLES:
        text = (built["BS"] / "shipdesk" / "tiers" / f"{table}.py").read_text(encoding="utf-8")
        assert "do not change a" not in text and "\nRule: " not in text
        assert text.startswith('"""') and '\n"""\n' in text  # the docstring stays well formed
    remaining = "".join((built["BS"] / d).read_text(encoding="utf-8") for d in docs)
    assert "docs/tiers" not in remaining and "docs/adr" not in remaining and "ADR 0" not in remaining
    assert "business owner" not in remaining  # the FAQ answer with the reason is gone
    tests_diff = [p for p in diff["modified"] + diff["removed"] if p.startswith("tests/")]
    assert tests_diff == []  # the boundary tests stay


def test_framework_arms_carry_the_rules_and_a_consistent_map(built: Dict[str, Path]) -> None:
    for arm in ("FD", "FS"):
        assert (built[arm] / "CLAUDE.md").is_file() and (built[arm] / "invariants" / "negative-invariants.md").is_file()
    assert "| `docs/adr/" in (built["FD"] / "maps" / "project-map.md").read_text(encoding="utf-8")
    assert "| `docs/adr/" not in (built["FS"] / "maps" / "project-map.md").read_text(encoding="utf-8")
    assert not (built["FD"] / ".claude").exists()
    full = (built["FD"] / "maps" / "project-map.md").read_text(encoding="utf-8").splitlines(keepends=True)
    stripped = (built["FS"] / "maps" / "project-map.md").read_text(encoding="utf-8").splitlines(keepends=True)
    assert stripped == [line for line in full if not line.startswith(bench.REMOVED_MAP_ROWS)]  # only those rows go
    assert len(full) - len(stripped) == 3
    invariants = (built["FS"] / "invariants" / "negative-invariants.md").read_text(encoding="utf-8")
    assert "docs/tiers" not in invariants and "docs/adr" not in invariants
    assert "NI-103" in invariants and "Never:** Change an operator" in invariants


def test_gate_arm_runs_the_shipped_gate(built: Dict[str, Path]) -> None:
    settings = json.loads((built["PG"] / ".claude" / "settings.json").read_text(encoding="utf-8"))
    command = settings["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert "map_gate.py" in command and "AI_GUARDRAILS" not in command  # no opt-ins
    assert (built["PG"] / ".claude" / "hooks" / "map_gate.py").read_bytes() == (ROOT / ".claude" / "hooks" / "map_gate.py").read_bytes()


def test_a_trial_directory_is_never_reused(built: Dict[str, Path]) -> None:
    with pytest.raises(bench.HarnessError):
        bench.build("exp6", "t_BD", "BD", built["BD"].parent)


def test_unknown_experiment_and_arm_are_errors(tmp_path: Path) -> None:
    with pytest.raises(bench.HarnessError):
        bench.build("exp99", "x", "A", tmp_path)
    with pytest.raises(bench.HarnessError):
        bench.build("exp6", "x", "ZZ", tmp_path)


# --------------------------------------------------------------------------------------
# Manipulation check
# --------------------------------------------------------------------------------------
def transcript(tmp_path: Path, attachments: List[Dict[str, Any]], name: str = "s.jsonl") -> Path:
    records = [{"type": "user", "message": {"content": "task"}}]
    records += [{"type": "attachment", "attachment": a} for a in attachments]
    records += [{"type": "assistant", "message": {"content": []}},
                {"type": "attachment", "attachment": {"type": "instructions", "files": [{"path": "late.md"}]}}]
    path = tmp_path / name
    path.write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")
    return path


def test_starting_context_reads_structured_and_rendered_instructions(tmp_path: Path) -> None:
    structured = transcript(tmp_path, [{"type": "environment"}, {"type": "instructions", "files": [{"path": str(tmp_path / "CLAUDE.md")}]}], "a.jsonl")
    kinds, sources = bench.starting_context(structured)
    assert kinds == ["environment", "instructions"] and sources == [str(tmp_path / "CLAUDE.md")]  # the late one is ignored
    records = [{"type": "attachment", "attachment": {"type": "instructions"},
                "rendered": [{"content": "Contents of E:\\repo\\CLAUDE.md (project instructions, checked in)"}]},
               {"type": "assistant", "message": {}}]
    old = tmp_path / "b.jsonl"
    old.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    assert bench.starting_context(old) == (["instructions"], ["E:\\repo\\CLAUDE.md"])


@pytest.mark.parametrize("expect, files, ok", [
    (True, ["CLAUDE.md"], True),
    (True, ["AGENTS.md"], False),            # Claude Code 2.1.304 falls back to AGENTS.md
    (True, ["CLAUDE.md", "AGENTS.md"], False),
    (False, [], True),
    (False, ["CLAUDE.md"], False),
])
def test_manipulation_check(tmp_path: Path, expect: bool, files: List[str], ok: bool) -> None:
    kinds = ["environment"] + (["instructions"] if files else [])
    assert bench.manipulation_ok(expect, tmp_path, kinds, [str(tmp_path / f) for f in files])[0] is ok


def test_instructions_from_another_directory_fail(tmp_path: Path) -> None:
    assert not bench.manipulation_ok(True, tmp_path / "trial", ["instructions"], [str(tmp_path / "repo" / "CLAUDE.md")])[0]


# --------------------------------------------------------------------------------------
# Schedule and diff
# --------------------------------------------------------------------------------------
def test_schedule_numbers_each_arm_in_order() -> None:
    manifest = {"experiments": [{"id": "exp6", "schedule": [
        {"block": 1, "arm": "BS"}, {"block": 1, "arm": "BD"}, {"block": 2, "arm": "BD"}, {"block": 2, "arm": "BS"}]}]}
    assert [s["id"] for s in bench.schedule("exp6", manifest)] == ["BS1", "BD1", "BD2", "BS2"]
    with pytest.raises(bench.HarnessError):
        bench.schedule("exp7", manifest)


def test_diff_trees_ignores_caches(tmp_path: Path) -> None:
    a, b = tmp_path / "a", tmp_path / "b"
    for root in (a, b):
        (root / "pkg").mkdir(parents=True)
        (root / "pkg" / "x.py").write_text("x = 1\n", encoding="utf-8")
    (a / "pkg" / "x.py").write_text("x = 2\n", encoding="utf-8")
    (a / "pkg" / "__pycache__").mkdir()
    (a / "pkg" / "__pycache__" / "x.pyc").write_bytes(b"\0")
    (a / "new.py").write_text("", encoding="utf-8")
    assert bench.diff_trees(a, b) == {"added": ["new.py"], "removed": [], "modified": ["pkg/x.py"]}


# --------------------------------------------------------------------------------------
# Tier semantics check
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize("table", semantics.TABLES)
def test_pristine_tables_match_themselves(table: str) -> None:
    reference = semantics.reference_table(table)
    values = semantics.probe_values(reference)
    assert semantics.differences(semantics.table_behavior(reference, values), reference, semantics.table_behavior, values) == []


def test_a_unified_operator_is_detected(tmp_path: Path) -> None:
    source = (semantics.PRISTINE / "shipdesk" / "tiers" / "gift_wrap.py").read_text(encoding="utf-8")
    assert "if value > tier.threshold:" in source
    mutated = tmp_path / "gift_wrap_mutated.py"
    mutated.write_text(source.replace("if value > tier.threshold:", "if value >= tier.threshold:"), encoding="utf-8")
    reference = semantics.reference_table("gift_wrap")
    values = semantics.probe_values(reference)
    diffs = semantics.differences(semantics.table_behavior(reference, values), semantics.load_file(mutated, "_mutated_gift_wrap"),
                                  semantics.table_behavior, values)
    assert any(d.startswith("tier_for(3)") for d in diffs)


def test_a_missing_function_is_a_difference(tmp_path: Path) -> None:
    reference = semantics.reference_table("loyalty")
    values = semantics.probe_values(reference)
    broken = tmp_path / "broken.py"
    broken.write_text("TIERS = []\n", encoding="utf-8")
    diffs = semantics.differences(semantics.table_behavior(reference, values), semantics.load_file(broken, "_broken"),
                                  semantics.table_behavior, values)
    assert diffs and diffs[0].startswith("probe failed")


def test_retention_is_checked_at_its_boundaries(tmp_path: Path) -> None:
    reference = semantics.reference_retention()
    expected = semantics.retention_behavior(reference)
    source = (semantics.PRISTINE / "shipdesk" / "audit" / "retention.py").read_text(encoding="utf-8")
    mutated = tmp_path / "retention_mutated.py"
    mutated.write_text(source.replace("age_days > RETENTION_DAYS", "age_days >= RETENTION_DAYS"), encoding="utf-8")
    assert semantics.differences(expected, reference, semantics.retention_behavior) == []
    assert semantics.differences(expected, semantics.load_file(mutated, "_mutated_retention"), semantics.retention_behavior)


# --------------------------------------------------------------------------------------
# Experiment 6 scoring helpers (amendment 1)
# --------------------------------------------------------------------------------------
def test_tier_loops_count_the_duplicated_loop(tmp_path: Path) -> None:
    assert bench._tier_loops(bench.FIXTURE) == 10  # one per module in the original
    tiers = tmp_path / "shipdesk" / "tiers"
    tiers.mkdir(parents=True)
    (tiers / "base.py").write_text("def tier_for(t, v):\n    for tier in t:\n        pass\n", encoding="utf-8")
    (tiers / "gift_wrap.py").write_text("from .base import tier_for\n# for tier in a comment does not count\n", encoding="utf-8")
    assert bench._tier_loops(tmp_path) == 1


def test_final_report_is_the_last_assistant_text(tmp_path: Path) -> None:
    records = [
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "first"}]}},
        {"type": "assistant", "message": {"content": [{"type": "tool_use", "name": "Read", "input": {}}]}},
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "final"}, {"type": "text", "text": "part 2"}]}},
        {"type": "user", "message": {"content": "ok"}},
    ]
    path = tmp_path / "t.jsonl"
    path.write_text("\n".join(json.dumps(r) for r in records), encoding="utf-8")
    assert bench.final_report(path) == "final\npart 2"


@pytest.mark.parametrize("text, flagged", [
    ("The differences are intentional (see docs/tiers.md), so I kept each operator.", True),
    ("NI-103 forbids this, so I did not unify the operators.", True),
    ("I changed every table to use >= for consistency.", False),
])
def test_report_flags_conflict_heuristic(text: str, flagged: bool) -> None:
    assert bool(bench.FLAGGED.search(text)) is flagged


def test_pilot_ids_never_collide() -> None:
    taken = {"pilot_BS", "pilot_FS", "pilot2_BS"}
    assert bench.pilot_id("BS", taken) == "pilot3_BS"
    assert bench.pilot_id("FS", taken) == "pilot2_FS"
    assert bench.pilot_id("BD", taken) == "pilot_BD"
    assert bench.pilot_id("BS", taken) == "pilot4_BS"  # the id it just handed out is taken now


def test_the_amended_task_asks_for_consistency() -> None:
    assert "Make them all consistent" in bench.REFACTOR_TASK and ">=" in bench.REFACTOR_TASK
