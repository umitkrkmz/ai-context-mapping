"""Tests for the benchmark reporting pipeline (benchmarks/analyze_transcripts.py) and its committed outputs.

The pipeline turns Claude Code transcripts into results.json and renders the markdown tables from it.
These tests build small synthetic transcripts, so they need no real agent runs, and they also check that
the committed results.json is internally consistent and that the tables in docs/benchmark-results.md are
exactly what results.json renders. Standard library plus pytest only.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import pytest

ROOT = Path(__file__).resolve().parents[1]
TOOL = ROOT / "benchmarks" / "analyze_transcripts.py"
RESULTS = ROOT / "benchmarks" / "results" / "results.json"
MANIFEST = ROOT / "benchmarks" / "results" / "manifest.json"
DOC = ROOT / "docs" / "benchmark-results.md"


def load_tool():
    spec = importlib.util.spec_from_file_location("analyze_transcripts", TOOL)
    module = importlib.util.module_from_spec(spec)
    sys.modules["analyze_transcripts"] = module
    spec.loader.exec_module(module)
    return module


tool = load_tool()


# --------------------------------------------------------------------------------------
# Synthetic transcripts
# --------------------------------------------------------------------------------------
def usage(inp: int = 10, out: int = 100, write: int = 1000, read: int = 5000) -> Dict[str, int]:
    return {"input_tokens": inp, "output_tokens": out, "cache_creation_input_tokens": write, "cache_read_input_tokens": read}


def assistant(msg_id: str, model: str, version: str, use: Dict[str, int], calls: Optional[List[Dict[str, Any]]] = None, ts: str = "2026-01-01T00:00:00Z") -> Dict[str, Any]:
    return {"type": "assistant", "timestamp": ts, "version": version,
            "message": {"id": msg_id, "model": model, "usage": use, "content": calls or []}}


def tool_use(call_id: str, name: str, **tool_input: Any) -> Dict[str, Any]:
    return {"type": "tool_use", "id": call_id, "name": name, "input": tool_input}


def result(call_id: str, text: str, ts: str = "2026-01-01T00:00:05Z") -> Dict[str, Any]:
    return {"type": "user", "timestamp": ts, "message": {"content": [{"type": "tool_result", "tool_use_id": call_id, "content": text}]}}


def write_transcript(directory: Path, agent_id: str, records: List[Dict[str, Any]]) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    (directory / f"agent-{agent_id}.jsonl").write_text("\n".join(json.dumps(r) for r in records) + "\n", encoding="utf-8")


def simple_agent(directory: Path, agent_id: str, cost_scale: int, model: str = "claude-test-1", version: str = "9.9.9") -> None:
    """A two-turn agent whose cost scales with ``cost_scale``."""
    write_transcript(directory, agent_id, [
        assistant("m1", model, version, usage(10, 100, 1000 * cost_scale, 5000), [tool_use("t1", "Read", file_path="a.py")], ts="2026-01-01T00:00:00Z"),
        result("t1", "x" * 400),
        assistant("m2", model, version, usage(10, 50, 0, 6000 * cost_scale), [], ts="2026-01-01T00:00:30Z"),
    ])


# --------------------------------------------------------------------------------------
# load_agent
# --------------------------------------------------------------------------------------
def test_weighted_cost_and_token_buckets(tmp_path: Path) -> None:
    write_transcript(tmp_path, "a1", [
        assistant("m1", "claude-test-1", "9.9.9", usage(10, 100, 1000, 5000)),
        assistant("m2", "claude-test-1", "9.9.9", usage(20, 40, 0, 8000)),
    ])
    info = tool.load_agent(str(tmp_path), "a1")
    assert info["usage"] == {"input": 30, "output": 140, "cache_write": 1000, "cache_read": 13000}
    assert info["new_tokens"] == 30 + 140 + 1000
    assert info["all_in_tokens"] == 30 + 140 + 1000 + 13000
    assert info["weighted_cost"] == round(30 + 1.25 * 1000 + 0.1 * 13000 + 5 * 140)
    custom = tool.load_agent(str(tmp_path), "a1", (1, 1, 1, 1))
    assert custom["weighted_cost"] == 30 + 140 + 1000 + 13000


def test_streamed_chunks_count_once_with_final_usage(tmp_path: Path) -> None:
    write_transcript(tmp_path, "a2", [
        assistant("m1", "claude-test-1", "9.9.9", usage(10, 1, 1000, 0)),
        assistant("m1", "claude-test-1", "9.9.9", usage(10, 90, 1000, 0)),  # same message, final counts
    ])
    info = tool.load_agent(str(tmp_path), "a2")
    assert info["turns"] == 1 and info["usage"]["output"] == 90


def test_model_and_client_version_come_from_the_transcript(tmp_path: Path) -> None:
    write_transcript(tmp_path, "a3", [
        assistant("m1", "claude-test-1", "1.2.3", usage()),
        assistant("m2", "claude-test-1", "1.2.3", usage()),
        assistant("m3", "claude-other", "1.2.3", usage()),
    ])
    info = tool.load_agent(str(tmp_path), "a3")
    assert info["model"] == "claude-test-1" and info["models_seen"] == ["claude-other", "claude-test-1"]
    assert info["client_version"] == "1.2.3"


def test_missing_metadata_is_none_not_an_error(tmp_path: Path) -> None:
    write_transcript(tmp_path, "a4", [{"type": "assistant", "message": {"id": "m1", "usage": usage(), "content": []}}])
    info = tool.load_agent(str(tmp_path), "a4")
    assert info["model"] is None and info["client_version"] is None


def test_search_output_and_blocked_calls(tmp_path: Path) -> None:
    write_transcript(tmp_path, "a5", [
        assistant("m1", "claude-test-1", "9.9.9", usage(), [tool_use("t1", "Glob", pattern="**/*")]),
        result("t1", "Rule 1 Enforced: Access denied. You must inspect the map."),
        assistant("m2", "claude-test-1", "9.9.9", usage(), [tool_use("t2", "Glob", pattern="**/*")]),
        result("t2", "Search suppressed: broad repository searches are disabled in this run."),
        assistant("m3", "claude-test-1", "9.9.9", usage(), [tool_use("t3", "Grep", pattern="x"), tool_use("t4", "Bash", command="grep -rn x .")]),
        result("t3", "g" * 800),
        result("t4", "s" * 400),
        assistant("m4", "claude-test-1", "9.9.9", usage(), [tool_use("t5", "Bash", command="cat a.py")]),
        result("t5", "r" * 4000),
    ])
    info = tool.load_agent(str(tmp_path), "a5")
    assert info["blocked_by_gate"] == 2
    assert info["search_output_tokens"] == (800 + 400) // 4  # blocked calls and file reads are excluded
    assert info["output_tokens_by_kind"]["shell-read"] == 1000


def test_transcript_span_and_missing_file(tmp_path: Path) -> None:
    simple_agent(tmp_path, "a6", 1)
    assert tool.load_agent(str(tmp_path), "a6")["transcript_span_s"] == 30.0
    with pytest.raises(FileNotFoundError):
        tool.load_agent(str(tmp_path), "nope")


# --------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------
def test_aggregate() -> None:
    assert tool.aggregate([1, 2, 3, 10]) == {"n": 4, "median": 2.5, "mean": 4.0, "min": 1.0, "max": 10.0}
    assert tool.aggregate([]) == {"n": 0, "median": None, "mean": None, "min": None, "max": None}


def test_permutation_p_values_are_exact() -> None:
    assert tool.permutation_p_values([10, 11, 12], [1, 2, 3]) == (0.05, 0.1)  # perfect separation, n=3
    assert tool.permutation_p_values([10, 11, 12, 13], [1, 2, 3, 4]) == (round(1 / 70, 4), round(2 / 70, 4))
    # Identical groups: 8 of the 20 splits tie exactly, so P(diff <= 0) = (12 / 2 + 8) / 20 = 0.7.
    assert tool.permutation_p_values([1, 2, 3], [1, 2, 3]) == (0.7, 1.0)
    assert tool.permutation_p_values([], [1]) == (None, None)


def test_permutation_direction_and_symmetry() -> None:
    lower, two_sided = tool.permutation_p_values([1, 2, 3], [10, 11, 12])  # b is more expensive
    assert lower == 1.0 and two_sided == 0.1
    assert tool.permutation_p_values([5, 6, 7, 20], [1, 2, 3, 4])[1] == tool.permutation_p_values([1, 2, 3, 4], [5, 6, 7, 20])[1]


def test_ratio_and_rates() -> None:
    assert tool._ratio(1, 4) == 0.25 and tool._ratio(None, 4) is None and tool._ratio(1, 0) is None
    assert tool._fraction_full(["8/8", "7/8", "8/8"]) == round(2 / 3, 4)
    assert tool._fraction_full([]) is None
    assert tool._rate([True, False, None, True]) == round(2 / 3, 4)


# --------------------------------------------------------------------------------------
# Building results, rendering, and updating documents
# --------------------------------------------------------------------------------------
def make_manifest(tmp_path: Path) -> Dict[str, Any]:
    directory = tmp_path / "transcripts"
    for agent, scale in (("g1", 10), ("g2", 12), ("g3", 11), ("h1", 5), ("h2", 6), ("h3", 4)):
        simple_agent(directory, agent, scale)
    scoring = {"acceptance": "8/8", "mutation": "4/4", "e2e_test_added": False, "opened_legacy_module": False}

    def trial(tid: str, arm: str, agent: str, order: int) -> Dict[str, Any]:
        return {"id": tid, "arm": arm, "agent_id": agent, "order": order, "harness": {"duration_ms": 20000 + order * 1000}, "scoring": scoring}

    return {
        "schema_version": 1, "transcripts_dir": str(directory),
        "weights": {"input": 1.0, "cache_write": 1.25, "cache_read": 0.1, "output": 5.0},
        "experiments": [{
            "id": "demo", "title": "Demo experiment", "date": "2026-01-01", "version": "v0", "fixture": "f", "project_tokens": 1,
            "arms": [{"id": "G", "label": "Slow arm"}, {"id": "H", "label": "Fast arm"}],
            "comparisons": [{"name": "Fast vs slow", "a": "G", "b": "H"}],
            "trials": [trial("G1", "G", "g1", 1), trial("H1", "H", "h1", 2), trial("G2", "G", "g2", 3),
                       trial("H2", "H", "h2", 4), trial("G3", "G", "g3", 5), trial("H3", "H", "h3", 6)],
        }],
    }


def test_build_results_aggregates_comparisons_and_model(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    results = tool.build_results(manifest, manifest["transcripts_dir"])
    assert results["environment"]["models"] == ["claude-test-1"] and results["environment"]["claude_code_versions"] == ["9.9.9"]
    exp = results["experiments"][0]
    assert [t["id"] for t in exp["trials"]] == ["G1", "H1", "G2", "H2", "G3", "H3"]  # manifest order
    g, h = exp["arms"][0]["summary"], exp["arms"][1]["summary"]
    assert g["n"] == 3 and h["n"] == 3
    assert h["metrics"]["weighted_cost"]["median"] < g["metrics"]["weighted_cost"]["median"]
    cost = exp["comparisons"][0]["metrics"]["weighted_cost"]
    assert cost["ratio_of_medians"] < 1 and cost["p_one_sided_lower"] == 0.05 and cost["p_two_sided"] == 0.1
    assert exp["trials"][0]["latency_s"] == 21.0  # harness duration wins over the transcript span
    assert g["quality"]["acceptance_full_rate"] == 1.0 and g["quality"]["e2e_test_rate"] == 0.0


def test_results_are_deterministic(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    first = tool.dump_json(tool.build_results(manifest, manifest["transcripts_dir"]))
    second = tool.dump_json(tool.build_results(manifest, manifest["transcripts_dir"]))
    assert first == second and first.endswith("\n")
    assert json.loads(first)["schema_version"] == 1
    assert "timestamp" not in first.lower().replace("first_timestamp", "").replace("last_timestamp", "")


def test_render_contains_the_numbers_and_is_deterministic(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    results = tool.build_results(manifest, manifest["transcripts_dir"])
    text = tool.render_block(results, "demo")
    assert text == tool.render_block(results, "demo")
    assert "`claude-test-1` (6 trials)" in text and "Fast vs slow" in text
    cost = results["experiments"][0]["trials"][0]["weighted_cost"]
    assert f"{cost:,}" in text
    assert "0.050" in text and "0.100" in text
    with pytest.raises(tool.ReportError):
        tool.render_block(results, "missing")


def test_update_document_replaces_only_the_marked_region_and_is_idempotent(tmp_path: Path) -> None:
    manifest = make_manifest(tmp_path)
    results = tool.build_results(manifest, manifest["transcripts_dir"])
    doc = "# Title\n\nintro text\n\n<!-- results:begin demo -->\nSTALE\n<!-- results:end demo -->\n\noutro text\n"
    once = tool.update_document(doc, results)
    assert "STALE" not in once and once.startswith("# Title\n\nintro text\n\n") and once.endswith("\n\noutro text\n")
    assert "Demo" not in once or "Fast vs slow" in once
    assert tool.update_document(once, results) == once


@pytest.mark.parametrize("doc", ["no markers here\n", "<!-- results:begin demo -->\nno end\n", "<!-- results:end demo -->\n<!-- results:begin demo -->\n"])
def test_update_document_rejects_bad_markers(tmp_path: Path, doc: str) -> None:
    manifest = make_manifest(tmp_path)
    results = tool.build_results(manifest, manifest["transcripts_dir"])
    with pytest.raises(tool.ReportError):
        tool.update_document(doc, results)


# --------------------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------------------
def test_cli_export_render_and_document_round_trip(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    manifest = make_manifest(tmp_path)
    manifest_path, results_path, doc_path = tmp_path / "manifest.json", tmp_path / "out" / "results.json", tmp_path / "doc.md"
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    doc_path.write_text("intro\n<!-- results:begin demo -->\nold\n<!-- results:end demo -->\n", encoding="utf-8")

    assert tool.main(["--export", str(manifest_path), "--out", str(results_path)]) == 0
    first_bytes = results_path.read_bytes()
    assert tool.main(["--export", str(manifest_path), "--out", str(results_path)]) == 0
    assert results_path.read_bytes() == first_bytes, "exporting twice must give identical bytes"

    assert tool.main(["--check-doc", str(doc_path), "--results", str(results_path)]) == 1  # stale
    assert tool.main(["--update-doc", str(doc_path), "--results", str(results_path)]) == 0
    assert tool.main(["--check-doc", str(doc_path), "--results", str(results_path)]) == 0
    capsys.readouterr()
    assert tool.main(["--render", str(results_path), "--experiment", "demo"]) == 0
    assert "Per-arm aggregates" in capsys.readouterr().out


def test_cli_reports_missing_inputs_with_exit_code_two(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    manifest = make_manifest(tmp_path)
    manifest["transcripts_dir"] = str(tmp_path / "nowhere")
    path = tmp_path / "manifest.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    assert tool.main(["--export", str(path), "--out", str(tmp_path / "r.json")]) == 2
    assert "transcript not found" in capsys.readouterr().err
    assert tool.main(["--render", str(tmp_path / "missing.json")]) == 2
    assert tool.main([]) == 2
    assert tool.main(["a1"]) == 2  # per-agent report needs --dir


def test_cli_per_agent_report_shows_model(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    simple_agent(tmp_path, "solo", 1)
    assert tool.main(["--dir", str(tmp_path), "solo"]) == 0
    out = capsys.readouterr().out
    assert "model: claude-test-1" in out and "client: 9.9.9" in out and "weighted cost" in out


# --------------------------------------------------------------------------------------
# The committed artifacts
# --------------------------------------------------------------------------------------
needs_results = pytest.mark.skipif(not RESULTS.is_file(), reason="benchmarks/results/results.json has not been generated yet")


@needs_results
def test_committed_results_have_model_and_environment_metadata() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert results["schema_version"] == 1
    assert results["environment"]["models"] and all(m.startswith("claude-") for m in results["environment"]["models"])
    assert results["environment"]["claude_code_versions"]
    assert {e["id"] for e in results["experiments"]} >= {"exp1", "exp2", "exp3", "exp4"}


@needs_results
def test_committed_aggregates_match_their_trials() -> None:
    """Hand-editing an aggregate, a ratio, or a p-value makes this fail."""
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    for exp in results["experiments"]:
        by_arm = {arm["id"]: [t for t in exp["trials"] if t["arm"] == arm["id"]] for arm in exp["arms"]}
        for arm in exp["arms"]:
            assert arm["summary"] == json.loads(json.dumps(tool.summarize_arm(by_arm[arm["id"]]))), (exp["id"], arm["id"])
        for cmp_ in exp["comparisons"]:
            expected = json.loads(json.dumps(tool.compare_arms(by_arm[cmp_["a"]], by_arm[cmp_["b"]])))
            assert cmp_["metrics"] == expected, (exp["id"], cmp_["name"])


@needs_results
def test_committed_results_match_the_manifest_and_preregistration() -> None:
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for m_exp, r_exp in zip(manifest["experiments"], results["experiments"]):
        assert m_exp["id"] == r_exp["id"]
        assert sorted(t["id"] for t in m_exp["trials"]) == sorted(t["id"] for t in r_exp["trials"])
    exp4 = next(e for e in results["experiments"] if e["id"] == "exp4")
    assert exp4["preregistration"]["recorded_before_any_trial"] is True
    assert exp4["preregistration"]["primary_metric"].startswith("weighted_cost")
    assert len(exp4["trials"]) == 16 and {a["id"] for a in exp4["arms"]} == {"A", "B", "C", "D"}


@needs_results
def test_documented_tables_match_results_json() -> None:
    """The tables in docs/benchmark-results.md are generated, so they must equal a fresh rendering."""
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    text = DOC.read_text(encoding="utf-8")
    assert "<!-- results:begin exp4 -->" in text, "docs/benchmark-results.md is missing the experiment 4 markers"
    assert tool.update_document(text, results) == text, "run: python benchmarks/analyze_transcripts.py --update-doc docs/benchmark-results.md"
