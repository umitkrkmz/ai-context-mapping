#!/usr/bin/env python3
"""Measure benchmark agents objectively from their Claude Code transcripts, and report the results.

Agent self-reports and single harness totals are hard to audit. A transcript records every tool call and
the token usage of every model turn, so this tool derives the numbers instead:

* tool calls by name, the files read, and the order in which they happened,
* token usage by type (input, output, cache write, cache read),
* a price-weighted cost, so that cheap cache reads and expensive output are not lumped together,
* how much search output was returned to the model, and how many calls a hook blocked,
* the exact model identifier and the Claude Code client version that produced the transcript.

Cost weights (in units of one uncached input token) are typical published ratios and are only an
assumption: input 1.0, cache write 1.25, cache read 0.1, output 5.0. Change them with --weights.

Modes:
    per-agent report     python benchmarks/analyze_transcripts.py --dir <dir> AGENT_ID [AGENT_ID ...]
    export everything    python benchmarks/analyze_transcripts.py --export benchmarks/results/manifest.json
    render tables        python benchmarks/analyze_transcripts.py --render benchmarks/results/results.json
    update a document    python benchmarks/analyze_transcripts.py --update-doc docs/benchmark-results.md
    check a document     python benchmarks/analyze_transcripts.py --check-doc docs/benchmark-results.md

``--export`` reads a manifest (which trials exist, their arms, the harness figures, and the scoring
outcomes we recorded), derives every metric from the transcripts, and writes ``results.json``: per-trial
metrics, per-arm aggregates, exact permutation tests for the comparisons, and the model metadata. The
markdown tables are rendered from ``results.json`` alone, so they can be regenerated without the
transcripts, and the output is deterministic (sorted keys, fixed rounding, no timestamps).
``--update-doc`` rewrites the text between ``<!-- results:begin ID -->`` and ``<!-- results:end ID -->``
markers; ``--check-doc`` exits 1 if a document is out of date.

Transcripts live in the ``subagents`` folder of a Claude Code session, for example
~/.claude/projects/<project>/<session>/subagents, as ``agent-<id>.jsonl`` files.

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import datetime
import itertools
import json
import os
import re
import statistics
import sys
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SCHEMA_VERSION = 1
DEFAULT_WEIGHTS = (1.0, 1.25, 0.1, 5.0)  # input, cache write, cache read, output
DEFAULT_MANIFEST = os.path.join("benchmarks", "results", "manifest.json")
DEFAULT_RESULTS = os.path.join("benchmarks", "results", "results.json")
GATE_MESSAGE = "Rule 1 Enforced"  # the map gate's block message (.claude/hooks/map_gate.py)
SUPPRESS_MESSAGE = "Search suppressed"  # the ablation mode's block message
BLOCK_MARKERS = (GATE_MESSAGE, SUPPRESS_MESSAGE)
SEARCH_COMMAND = re.compile(r"(^|[\s;&|(])(grep|egrep|fgrep|rg|ag|ack|find|fd|tree)\b|ls\s+-\w*R")
READ_COMMAND = re.compile(r"\b(cat|head|tail|sed|less|more|nl|bat|Get-Content|type)\b")
MARKER = "<!-- results:{kind} {experiment} -->"
COMPARED_METRICS = ("weighted_cost", "new_tokens", "search_output_tokens", "tool_calls")


class ReportError(Exception):
    """A problem with the manifest, the results file, or a document (exit code 2)."""


# --------------------------------------------------------------------------------------
# Transcript parsing
# --------------------------------------------------------------------------------------
def _parse_time(stamp: Optional[str]) -> Optional[datetime.datetime]:
    if not stamp:
        return None
    try:
        return datetime.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_agent(directory: str, agent_id: str, weights: Sequence[float] = DEFAULT_WEIGHTS) -> Dict[str, Any]:
    """Parse one transcript and return its metrics."""
    path = os.path.join(os.path.expanduser(directory), f"agent-{agent_id}.jsonl")
    if not os.path.isfile(path):
        raise FileNotFoundError(path)
    per_message: Dict[str, Dict[str, int]] = {}
    calls: List[Tuple[str, str]] = []
    seen_calls = set()
    call_kind: Dict[str, str] = {}
    output_chars: Dict[str, int] = {}
    models: Dict[str, int] = {}
    versions: Dict[str, int] = {}
    blocked = 0
    first_ts: Optional[str] = None
    last_ts: Optional[str] = None
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                record = json.loads(line)
            except ValueError:
                continue
            stamp = record.get("timestamp")
            if stamp:
                first_ts = first_ts or stamp
                last_ts = stamp
            if record.get("version"):
                versions[str(record["version"])] = versions.get(str(record["version"]), 0) + 1
            message = record.get("message") or {}
            if record.get("type") == "user" and isinstance(message.get("content"), list):
                for block in message["content"]:
                    if isinstance(block, dict) and block.get("type") == "tool_result":
                        raw = block.get("content")
                        text = raw if isinstance(raw, str) else json.dumps(raw)
                        if any(marker in text for marker in BLOCK_MARKERS):
                            blocked += 1  # a blocked call returns only the hook's message, not search output
                            continue
                        kind = call_kind.get(block.get("tool_use_id"), "other")
                        output_chars[kind] = output_chars.get(kind, 0) + len(text)
                continue
            if record.get("type") != "assistant":
                continue
            if message.get("model"):
                models[str(message["model"])] = models.get(str(message["model"]), 0) + 1
            usage = message.get("usage") or {}
            # Streamed chunks repeat the message id; the last chunk holds the final counts.
            per_message[message.get("id") or record.get("uuid") or str(len(per_message))] = {
                "input": usage.get("input_tokens", 0),
                "output": usage.get("output_tokens", 0),
                "cache_write": usage.get("cache_creation_input_tokens", 0),
                "cache_read": usage.get("cache_read_input_tokens", 0),
            }
            content = message.get("content")
            for block in content if isinstance(content, list) else []:
                if isinstance(block, dict) and block.get("type") == "tool_use" and block.get("id") not in seen_calls:
                    seen_calls.add(block.get("id"))
                    tool_input = block.get("input") or {}
                    target = tool_input.get("file_path") or tool_input.get("pattern") or tool_input.get("command") or ""
                    name = str(block.get("name"))
                    calls.append((name, str(target).replace("\n", " ")[:120]))
                    command = str(tool_input.get("command") or "")
                    if name in ("Bash", "PowerShell"):
                        kind = "shell-search" if SEARCH_COMMAND.search(command) else "shell-read" if READ_COMMAND.search(command) else "shell-other"
                    else:
                        kind = name
                    call_kind[block.get("id")] = kind
    totals = {"input": 0, "output": 0, "cache_write": 0, "cache_read": 0}
    for usage in per_message.values():
        for key in totals:
            totals[key] += usage[key]
    w_in, w_write, w_read, w_out = weights
    by_tool: Dict[str, int] = {}
    for name, _target in calls:
        by_tool[name] = by_tool.get(name, 0) + 1
    started, ended = _parse_time(first_ts), _parse_time(last_ts)
    span = round((ended - started).total_seconds(), 1) if started and ended else None
    return {
        "agent": agent_id,
        "model": max(models, key=lambda m: (models[m], m)) if models else None,
        "models_seen": sorted(models),
        "client_version": max(versions, key=lambda v: (versions[v], v)) if versions else None,
        "turns": len(per_message),
        "tool_calls": len(calls),
        "by_tool": by_tool,
        "files_read": [target for name, target in calls if name == "Read"],
        "sequence": calls,
        "blocked_by_gate": blocked,
        "output_tokens_by_kind": {kind: chars // 4 for kind, chars in sorted(output_chars.items())},
        "search_output_tokens": sum(c for k, c in output_chars.items() if k in ("Grep", "Glob", "shell-search")) // 4,
        "usage": totals,
        "new_tokens": totals["input"] + totals["output"] + totals["cache_write"],
        "all_in_tokens": sum(totals.values()),
        "weighted_cost": round(
            w_in * totals["input"] + w_write * totals["cache_write"] + w_read * totals["cache_read"] + w_out * totals["output"]
        ),
        "transcript_span_s": span,
        "first_timestamp": first_ts,
        "last_timestamp": last_ts,
    }


# --------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------
def aggregate(values: Sequence[float]) -> Dict[str, Any]:
    """n, median, mean, min, and max, rounded so the output is stable."""
    if not values:
        return {"n": 0, "median": None, "mean": None, "min": None, "max": None}
    return {
        "n": len(values),
        "median": round(float(statistics.median(values)), 2),
        "mean": round(float(statistics.mean(values)), 2),
        "min": round(float(min(values)), 2),
        "max": round(float(max(values)), 2),
    }


def permutation_p_values(a: Sequence[float], b: Sequence[float]) -> Tuple[Optional[float], Optional[float]]:
    """Exact permutation test on the difference of means (b minus a).

    Returns ``(p_lower, p_two_sided)``: the chance of a difference at least as low as observed (a one-sided
    test that b is cheaper than a), and of one at least as large in magnitude. Every reassignment of the
    pooled values into groups of the original sizes is enumerated, so the result is exact and
    deterministic. With n = 3 per arm the smallest one-sided p is 1/20; with n = 4 it is 1/70.
    """
    if not a or not b:
        return None, None
    pooled = list(a) + list(b)
    size_b = len(b)
    observed = statistics.mean(b) - statistics.mean(a)
    total = lower = extreme = 0
    for chosen in itertools.combinations(range(len(pooled)), size_b):
        picked = set(chosen)
        mean_b = sum(pooled[i] for i in chosen) / size_b
        mean_a = sum(pooled[i] for i in range(len(pooled)) if i not in picked) / len(a)
        diff = mean_b - mean_a
        total += 1
        if diff <= observed + 1e-9:
            lower += 1
        if abs(diff) >= abs(observed) - 1e-9:
            extreme += 1
    return round(lower / total, 4), round(extreme / total, 4)


def _ratio(numerator: Optional[float], denominator: Optional[float]) -> Optional[float]:
    if numerator is None or not denominator:
        return None
    return round(numerator / denominator, 4)


def _fraction_full(values: Iterable[str]) -> Optional[float]:
    """Share of "a/b" strings with a == b (for example acceptance "8/8")."""
    items = list(values)
    if not items:
        return None
    full = 0
    for text in items:
        left, _, right = str(text).partition("/")
        full += left.strip() == right.strip() and left.strip() != ""
    return round(full / len(items), 4)


def _rate(values: Iterable[Any]) -> Optional[float]:
    items = [v for v in values if v is not None]
    return round(sum(1 for v in items if v) / len(items), 4) if items else None


# --------------------------------------------------------------------------------------
# Building results.json from a manifest
# --------------------------------------------------------------------------------------
def trial_metrics(trial: Dict[str, Any], directory: str, weights: Sequence[float]) -> Dict[str, Any]:
    """Derive one trial's numbers from its transcript, merged with the manifest's harness and scoring data."""
    parsed = load_agent(directory, str(trial["agent_id"]), weights)
    harness = trial.get("harness") or {}
    latency = harness.get("duration_ms")
    scoring = trial.get("scoring") or {}
    return {
        "id": trial["id"],
        "arm": trial["arm"],
        "order": trial.get("order"),
        "agent_id": trial["agent_id"],
        "model": parsed["model"],
        "client_version": parsed["client_version"],
        "weighted_cost": parsed["weighted_cost"],
        "new_tokens": parsed["new_tokens"],
        "all_in_tokens": parsed["all_in_tokens"],
        "cache_read_tokens": parsed["usage"]["cache_read"],
        "output_tokens": parsed["usage"]["output"],
        "search_output_tokens": parsed["search_output_tokens"],
        "blocked_calls": parsed["blocked_by_gate"],
        "tool_calls": parsed["tool_calls"],
        "turns": parsed["turns"],
        "latency_s": round(latency / 1000, 1) if latency else parsed["transcript_span_s"],
        "harness_subagent_tokens": harness.get("subagent_tokens"),
        "acceptance": scoring.get("acceptance"),
        "mutation": scoring.get("mutation"),
        "e2e_test_added": scoring.get("e2e_test_added"),
        "opened_legacy_module": scoring.get("opened_legacy_module"),
    }


NUMERIC_METRICS = (
    "weighted_cost", "new_tokens", "all_in_tokens", "cache_read_tokens", "search_output_tokens",
    "blocked_calls", "tool_calls", "turns", "latency_s",
)


def summarize_arm(trials: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "n": len(trials),
        "metrics": {name: aggregate([t[name] for t in trials if t.get(name) is not None]) for name in NUMERIC_METRICS},
        "quality": {
            "acceptance_full_rate": _fraction_full(t["acceptance"] for t in trials if t.get("acceptance")),
            "mutation_full_rate": _fraction_full(t["mutation"] for t in trials if t.get("mutation")),
            "e2e_test_rate": _rate(t.get("e2e_test_added") for t in trials),
            "opened_legacy_rate": _rate(t.get("opened_legacy_module") for t in trials),
        },
    }


def compare_arms(a_trials: List[Dict[str, Any]], b_trials: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ratios (b over a) and exact permutation p-values for the metrics in COMPARED_METRICS."""
    out: Dict[str, Any] = {}
    for name in COMPARED_METRICS:
        a_vals = [t[name] for t in a_trials if t.get(name) is not None]
        b_vals = [t[name] for t in b_trials if t.get(name) is not None]
        a_agg, b_agg = aggregate(a_vals), aggregate(b_vals)
        p_lower, p_two = permutation_p_values(a_vals, b_vals)
        out[name] = {
            "ratio_of_medians": _ratio(b_agg["median"], a_agg["median"]),
            "ratio_of_means": _ratio(b_agg["mean"], a_agg["mean"]),
            "p_one_sided_lower": p_lower,
            "p_two_sided": p_two,
        }
    return out


def build_results(manifest: Dict[str, Any], directory: str) -> Dict[str, Any]:
    """Turn a manifest plus the transcripts it points to into the full results structure."""
    weights_cfg = manifest.get("weights") or {}
    weights = (
        weights_cfg.get("input", DEFAULT_WEIGHTS[0]), weights_cfg.get("cache_write", DEFAULT_WEIGHTS[1]),
        weights_cfg.get("cache_read", DEFAULT_WEIGHTS[2]), weights_cfg.get("output", DEFAULT_WEIGHTS[3]),
    )
    experiments: List[Dict[str, Any]] = []
    models: Dict[str, int] = {}
    versions: Dict[str, int] = {}
    for exp in manifest.get("experiments", []):
        trials = sorted((trial_metrics(t, directory, weights) for t in exp.get("trials", [])), key=lambda t: (t["order"] or 0, t["id"]))
        for trial in trials:
            if trial["model"]:
                models[trial["model"]] = models.get(trial["model"], 0) + 1
            if trial["client_version"]:
                versions[trial["client_version"]] = versions.get(trial["client_version"], 0) + 1
        arms = []
        for arm in exp.get("arms", []):
            arm_trials = [t for t in trials if t["arm"] == arm["id"]]
            arms.append({**arm, "summary": summarize_arm(arm_trials)})
        by_arm = {arm["id"]: [t for t in trials if t["arm"] == arm["id"]] for arm in exp.get("arms", [])}
        comparisons = [
            {**cmp_, "metrics": compare_arms(by_arm.get(cmp_["a"], []), by_arm.get(cmp_["b"], []))} for cmp_ in exp.get("comparisons", [])
        ]
        experiments.append({
            **{k: exp[k] for k in ("id", "title", "date", "version", "fixture", "project_tokens") if k in exp},
            **({"preregistration": exp["preregistration"]} if "preregistration" in exp else {}),
            **({"schedule": exp["schedule"]} if "schedule" in exp else {}),
            "arms": arms, "comparisons": comparisons, "trials": trials,
        })
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_by": "benchmarks/analyze_transcripts.py",
        "environment": {
            "models": sorted(models),
            "model_trial_counts": dict(sorted(models.items())),
            "claude_code_versions": sorted(versions),
        },
        "weights": {"input": weights[0], "cache_write": weights[1], "cache_read": weights[2], "output": weights[3]},
        "experiments": experiments,
    }


def dump_json(data: Dict[str, Any]) -> str:
    return json.dumps(data, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


# --------------------------------------------------------------------------------------
# Markdown rendering (from results.json alone)
# --------------------------------------------------------------------------------------
def _n(value: Optional[float], digits: int = 0) -> str:
    return "n/a" if value is None else f"{value:,.{digits}f}"


def _range(agg: Dict[str, Any], digits: int = 0) -> str:
    if agg["n"] == 0:
        return "n/a"
    return f"{_n(agg['median'], digits)} ({_n(agg['min'], digits)}-{_n(agg['max'], digits)})"


def _pct(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{round(value * 100):d}%"


def _ratio_text(value: Optional[float]) -> str:
    return "n/a" if value is None else f"{value:.2f}x"


def render_experiment(exp: Dict[str, Any]) -> str:
    """Render the per-trial, per-arm, and comparison tables for one experiment."""
    lines: List[str] = []
    labels = {arm["id"]: arm["label"] for arm in exp["arms"]}
    lines += [
        "**Per-trial results** (all values derived from transcripts)", "",
        "| Trial | Arm | Weighted cost | New tokens | Cache reads | Search output | Blocked | Tool calls | Turns | Latency | Acceptance | Mutation |",
        "| ----- | --- | ------------: | ---------: | ----------: | ------------: | ------: | ---------: | ----: | ------: | ---------- | -------- |",
    ]
    for t in exp["trials"]:
        lines.append(
            f"| {t['id']} | {t['arm']} | {_n(t['weighted_cost'])} | {_n(t['new_tokens'])} | {_n(t['cache_read_tokens'])} | "
            f"~{_n(t['search_output_tokens'])} | {t['blocked_calls']} | {t['tool_calls']} | {t['turns']} | {_n(t['latency_s'], 1)} s | "
            f"{t.get('acceptance') or 'n/a'} | {t.get('mutation') or 'n/a'} |"
        )
    lines += [
        "", "**Per-arm aggregates** (median, with the range in parentheses)", "",
        "| Arm | n | Weighted cost | New tokens | Search output | Tool calls | Turns | Latency (s) | 8/8 acceptance | 4/4 mutants | End-to-end test | Opened legacy module |",
        "| --- | -: | ------------: | ---------: | ------------: | ---------: | ----: | ----------: | -------------: | ----------: | --------------: | -------------------: |",
    ]
    for arm in exp["arms"]:
        s, m, q = arm["summary"], arm["summary"]["metrics"], arm["summary"]["quality"]
        lines.append(
            f"| {arm['id']}: {labels[arm['id']]} | {s['n']} | {_range(m['weighted_cost'])} | {_range(m['new_tokens'])} | "
            f"{_range(m['search_output_tokens'])} | {_range(m['tool_calls'])} | {_range(m['turns'])} | {_range(m['latency_s'], 1)} | "
            f"{_pct(q['acceptance_full_rate'])} | {_pct(q['mutation_full_rate'])} | {_pct(q['e2e_test_rate'])} | {_pct(q['opened_legacy_rate'])} |"
        )
    if exp["comparisons"]:
        lines += [
            "", "**Comparisons** (ratio of the second arm to the first; p-values are exact permutation tests on mean weighted cost)", "",
            "| Comparison | Cost, ratio of medians | Cost, ratio of means | p (one-sided, cheaper) | p (two-sided) | New tokens, ratio of medians | Search output, ratio of medians |",
            "| ---------- | ---------------------: | -------------------: | ---------------------: | ------------: | ---------------------------: | -----------------------------: |",
        ]
        for c in exp["comparisons"]:
            cost, new, search = c["metrics"]["weighted_cost"], c["metrics"]["new_tokens"], c["metrics"]["search_output_tokens"]
            p_low = "n/a" if cost["p_one_sided_lower"] is None else f"{cost['p_one_sided_lower']:.3f}"
            p_two = "n/a" if cost["p_two_sided"] is None else f"{cost['p_two_sided']:.3f}"
            lines.append(
                f"| {c['name']} | {_ratio_text(cost['ratio_of_medians'])} | {_ratio_text(cost['ratio_of_means'])} | {p_low} | {p_two} | "
                f"{_ratio_text(new['ratio_of_medians'])} | {_ratio_text(search['ratio_of_medians'])} |"
            )
    return "\n".join(lines) + "\n"


def render_environment(results: Dict[str, Any]) -> str:
    env = results["environment"]
    models = ", ".join(f"`{m}` ({env['model_trial_counts'][m]} trials)" for m in env["models"]) or "unknown"
    versions = ", ".join(f"`{v}`" for v in env["claude_code_versions"]) or "unknown"
    weights = results["weights"]
    return (
        f"Model: {models}. Claude Code client: {versions}. Cost weights: input {weights['input']:g}, cache write "
        f"{weights['cache_write']:g}, cache read {weights['cache_read']:g}, output {weights['output']:g}.\n"
    )


def render_block(results: Dict[str, Any], experiment: str) -> str:
    exp = next((e for e in results["experiments"] if e["id"] == experiment), None)
    if exp is None:
        raise ReportError(f"experiment {experiment!r} is not in the results")
    return f"{render_environment(results)}\n{render_experiment(exp)}"


def update_document(text: str, results: Dict[str, Any]) -> str:
    """Replace the text between results markers with freshly rendered tables."""
    updated = text
    found = 0
    for exp in results["experiments"]:
        begin, end = MARKER.format(kind="begin", experiment=exp["id"]), MARKER.format(kind="end", experiment=exp["id"])
        if begin not in updated:
            continue
        if end not in updated or updated.index(end) < updated.index(begin):
            raise ReportError(f"marker {begin!r} has no matching {end!r}")
        head, rest = updated.split(begin, 1)
        _old, tail = rest.split(end, 1)
        updated = f"{head}{begin}\n{render_block(results, exp['id'])}{end}{tail}"
        found += 1
    if not found:
        raise ReportError("the document has no results markers (<!-- results:begin ID -->)")
    return updated


# --------------------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="analyze_transcripts.py",
        description="Derive metrics from Claude Code agent transcripts, export results.json, and render report tables.",
    )
    parser.add_argument("agents", nargs="*", metavar="AGENT_ID", help="agent ids for the per-agent report")
    parser.add_argument("--dir", help="directory that holds agent-<id>.jsonl files (overrides the manifest's transcripts_dir)")
    parser.add_argument("--weights", nargs=4, type=float, metavar=("IN", "WRITE", "READ", "OUT"), default=DEFAULT_WEIGHTS,
                        help="cost weights for the per-agent report (default: 1 1.25 0.1 5)")
    parser.add_argument("--sequence", action="store_true", help="per-agent report: also print every tool call in order")
    parser.add_argument("--json", action="store_true", help="per-agent report: print machine-readable JSON")
    parser.add_argument("--export", metavar="MANIFEST", nargs="?", const=DEFAULT_MANIFEST, help=f"build results.json from a manifest (default {DEFAULT_MANIFEST})")
    parser.add_argument("--out", default=DEFAULT_RESULTS, help=f"where --export writes results.json (default {DEFAULT_RESULTS})")
    parser.add_argument("--render", metavar="RESULTS", nargs="?", const=DEFAULT_RESULTS, help="print markdown tables from a results.json")
    parser.add_argument("--experiment", help="limit --render to one experiment id (default: all)")
    parser.add_argument("--update-doc", metavar="DOC", help="rewrite the results markers in DOC from --results")
    parser.add_argument("--check-doc", metavar="DOC", help="exit 1 when DOC's results markers differ from --results")
    parser.add_argument("--results", default=DEFAULT_RESULTS, help=f"results.json used by --update-doc and --check-doc (default {DEFAULT_RESULTS})")
    return parser


def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as handle:
            return json.load(handle)
    except (OSError, ValueError) as exc:
        raise ReportError(f"cannot read {path}: {exc}") from exc


def run_export(args: argparse.Namespace) -> int:
    manifest = _load_json(args.export)
    directory = args.dir or manifest.get("transcripts_dir")
    if not directory:
        raise ReportError("no transcript directory: pass --dir or set transcripts_dir in the manifest")
    try:
        results = build_results(manifest, directory)
    except FileNotFoundError as exc:
        raise ReportError(f"transcript not found: {exc}") from exc
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(dump_json(results))
    trials = sum(len(e["trials"]) for e in results["experiments"])
    print(f"wrote {args.out}: {len(results['experiments'])} experiments, {trials} trials, models {results['environment']['models']}")
    return 0


def run_render(args: argparse.Namespace) -> int:
    results = _load_json(args.render)
    ids = [args.experiment] if args.experiment else [e["id"] for e in results["experiments"]]
    for index, experiment in enumerate(ids):
        exp = next((e for e in results["experiments"] if e["id"] == experiment), None)
        if exp is None:
            raise ReportError(f"experiment {experiment!r} is not in the results")
        sys.stdout.write(("\n" if index else "") + f"### {exp['title']}\n\n" + render_block(results, experiment))
    return 0


def run_doc(args: argparse.Namespace, check: bool) -> int:
    path = args.check_doc if check else args.update_doc
    results = _load_json(args.results)
    try:
        with open(path, encoding="utf-8") as handle:
            text = handle.read()
    except OSError as exc:
        raise ReportError(f"cannot read {path}: {exc}") from exc
    updated = update_document(text, results)
    if check:
        if updated != text:
            print(f"{path} is out of date; run: python benchmarks/analyze_transcripts.py --update-doc {path}", file=sys.stderr)
            return 1
        print(f"{path} matches {args.results}")
        return 0
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(updated)
    print(f"updated {path}" if updated != text else f"{path} already up to date")
    return 0


def run_agents(args: argparse.Namespace) -> int:
    if not args.dir:
        raise ReportError("--dir is required for the per-agent report")
    results = []
    for agent_id in args.agents:
        try:
            results.append(load_agent(args.dir, agent_id, tuple(args.weights)))
        except FileNotFoundError as exc:
            raise ReportError(f"transcript not found: {exc}") from exc
    if args.json:
        print(json.dumps(results, indent=2))
        return 0
    for item in results:
        usage = item["usage"]
        print(f"agent {item['agent']}: {item['turns']} turns, {item['tool_calls']} tool calls {item['by_tool']}")
        print(f"  model: {item['model']} | client: {item['client_version']}")
        print(
            f"  tokens: new {item['new_tokens']:,} (input {usage['input']:,}, output {usage['output']:,}, "
            f"cache write {usage['cache_write']:,}) | cache read {usage['cache_read']:,} | all-in {item['all_in_tokens']:,}"
        )
        print(f"  weighted cost: {item['weighted_cost']:,} input-token units")
        print(f"  search output returned to the model: ~{item['search_output_tokens']:,} tokens | calls blocked by a hook: {item['blocked_by_gate']}")
        print(f"  files read ({len(item['files_read'])}): {', '.join(item['files_read'])}")
        if args.sequence:
            for index, (name, target) in enumerate(item["sequence"], start=1):
                print(f"    {index:>2}. {name:<10} {target}")
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.export:
            return run_export(args)
        if args.render:
            return run_render(args)
        if args.update_doc:
            return run_doc(args, check=False)
        if args.check_doc:
            return run_doc(args, check=True)
        if args.agents:
            return run_agents(args)
        build_parser().print_usage(sys.stderr)
        print("error: give agent ids with --dir, or one of --export, --render, --update-doc, --check-doc", file=sys.stderr)
        return 2
    except ReportError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
