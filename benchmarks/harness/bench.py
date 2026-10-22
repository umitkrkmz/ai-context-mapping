#!/usr/bin/env python3
"""Benchmark harness: build trial projects, run one headless Claude Code session per trial, check, score, record.

Each trial is a fresh copy of the fixture, built for its arm, and runs as its own ``claude -p`` session whose
working directory is that copy. Only the copy's own instructions can load, as for a real adopter (see
docs/benchmark-results.md, sections 12 and 13). The pre-registered design (arms, schedule) is read from
benchmarks/results/manifest.json; the arm recipes live in EXPERIMENTS below.

Usage:
    python benchmarks/harness/bench.py status EXP
    python benchmarks/harness/bench.py build  EXP TRIAL_ID ARM          build one trial directory and stop
    python benchmarks/harness/bench.py pilot  EXP ARM [ARM ...]         run pilot trials (never pooled)
    python benchmarks/harness/bench.py next   EXP [COUNT]               run the next scheduled trials
    python benchmarks/harness/bench.py score  EXP                       score every logged trial
    python benchmarks/harness/bench.py record EXP                       write scored trials into the manifest

Options: --work DIR (trial copies and logs; default <system temp>/ai-context-mapping-bench),
--claude PATH (Claude Code CLI; default $AI_BENCH_CLAUDE or "claude"), --python PATH (interpreter with pytest
for the agents and the scorer; default $AI_BENCH_PYTHON or this interpreter).

A trial whose starting context fails the manipulation check stops the run (pre-registered stop rule).
This file launches processes, so it is exempt from NI-002 by name; it is benchmark tooling, never shipped.
"""
from __future__ import annotations

import argparse
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import uuid
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple

REPO = Path(__file__).resolve().parents[2]
BENCH = REPO / "benchmarks"
FIXTURE = BENCH / "shipdesk-large"
OVERLAY = BENCH / "shipdesk-large-overlay"
MANIFEST = BENCH / "results" / "manifest.json"
IGNORE = shutil.ignore_patterns("__pycache__", ".pytest_cache", "*.pyc")
SKIP_DIRS = {"__pycache__", ".pytest_cache"}
TIMEOUT_S = 1200

INTRO = """You are a software engineer working on a Python project located at:

    {dir}

Treat that directory as the whole world: do not read, search, or modify anything outside it. To run Python and the tests, use this interpreter (it has pytest installed):

    {py} -m pytest -q

Follow any contributor instructions the project itself contains.
"""

BUGFIX_TASK = """
BUG REPORT
"Customers whose cart subtotal (after discounts) is exactly $50.00 are being charged shipping. Company policy says free shipping applies at $50.00 or more."

TASK
Find the root cause, fix it, and add a regression test. Keep the change minimal.

When you are done, reply with a short report containing:
1. The root cause.
2. The files you changed.
3. The regression test you added (file path and test function names).
4. Anything you were unsure about, or deliberately chose not to change.
5. A list of every file you opened or read during the task (be complete and honest)."""

REFACTOR_TASK = """
TASK
The ten modules in shipdesk/tiers/ are near-identical copies of each other. Remove the duplication: move the shared logic into one place and make the tier modules use it.

When you are done, reply with a short report containing:
1. What you changed and why.
2. The files you changed.
3. Anything you were unsure about, or deliberately chose not to change.
4. A list of every file you opened or read during the task (be complete and honest)."""

GATE_SETTINGS = {
    "hooks": {
        "PreToolUse": [{
            "matcher": "Grep|Glob|Read|Bash|PowerShell|mcp__.*",
            "hooks": [{
                "type": "command",
                "command": "cd \"$CLAUDE_PROJECT_DIR\" || exit 0; if python3 -c 0 >/dev/null 2>&1; then PY=python3; else PY=python; fi; "
                           "exec \"$PY\" .claude/hooks/map_gate.py",
                "timeout": 10,
            }],
        }]
    }
}

CLAUDE_FLAGS = [
    "--model", "claude-sonnet-5",
    "--setting-sources", "project",
    "--strict-mcp-config",
    "--disable-slash-commands",
    "--permission-mode", "acceptEdits",
    "--allowedTools", "Bash,PowerShell,Read,Edit,Write,Glob,Grep",
    "--output-format", "json",
]

# Docstring guidance removed by the "strip" step: the "Rule:" line and the warning not to change an operator.
TIER_GUIDANCE = re.compile(r"\n\nRule: .*?another table\.\n\"\"\"", re.DOTALL)


class HarnessError(Exception):
    """A problem with the harness inputs (exit code 2)."""


# --------------------------------------------------------------------------------------
# Building trial directories
# --------------------------------------------------------------------------------------
def _edit_map(dest: Path, edit: Callable[[str], str]) -> None:
    path = dest / "maps" / "project-map.md"
    with open(path, encoding="utf-8", newline="") as handle:
        text = handle.read()
    with open(path, "w", encoding="utf-8", newline="") as handle:
        handle.write(edit(text))


def add_framework(dest: Path) -> None:
    """The framework layer: CLAUDE.md, AGENTS.md, map, invariants, guardrail scripts, MCP server, map test."""
    shutil.copytree(OVERLAY, dest, dirs_exist_ok=True, ignore=IGNORE)
    for name in ("scripts", "mcp"):
        shutil.copytree(REPO / name, dest / name, ignore=IGNORE)
    shutil.copy2(REPO / ".agentignore", dest)
    shutil.copy2(REPO / "templates" / "python" / "tests" / "test_maps.py", dest / "tests" / "test_maps.py")


def add_gate(dest: Path) -> None:
    """The project's own map gate, as shipped (no opt-ins), plus map rows for its files."""
    hooks = dest / ".claude" / "hooks"
    hooks.mkdir(parents=True)
    shutil.copy2(REPO / ".claude" / "hooks" / "map_gate.py", hooks)
    (dest / ".claude" / "settings.json").write_text(json.dumps(GATE_SETTINGS, indent=2), encoding="utf-8")
    rows = (
        "| `.claude/` | config | Claude Code project settings and hooks. | - |\n"
        "| `.claude/hooks/` | script | Claude Code hook scripts. | - |\n"
        "| `.claude/hooks/map_gate.py` | script | PreToolUse hook: blocks repository searches until the map is read. | - |\n"
        "| `.claude/settings.json` | config | Registers the map gate hook. | - |\n"
    )
    anchor = "| `AGENTS.md` |"

    def edit(text: str) -> str:
        if text.count(anchor) != 1:
            raise HarnessError("overlay map has no unique AGENTS.md row")
        return text.replace(anchor, rows + anchor)

    _edit_map(dest, edit)


def strip_guidance(dest: Path) -> None:
    """Remove the written reasons not to unify tier operators: tier docstring guidance and the ADRs.

    Code behavior, the tests, and the product spec (docs/tiers.md, docs/tiers/) are untouched.
    """
    tiers = sorted((dest / "shipdesk" / "tiers").glob("*.py"))
    stripped = 0
    for path in tiers:
        with open(path, encoding="utf-8", newline="") as handle:
            text = handle.read()
        new, count = TIER_GUIDANCE.subn('\n"""', text, count=1)
        if count:
            stripped += 1
            with open(path, "w", encoding="utf-8", newline="") as handle:
                handle.write(new)
    if stripped != 10:
        raise HarnessError(f"expected guidance in 10 tier modules, found {stripped}")
    shutil.rmtree(dest / "docs" / "adr")
    if (dest / "maps" / "project-map.md").is_file():
        def edit(text: str) -> str:
            lines = text.splitlines(keepends=True)
            kept = [line for line in lines if not line.startswith("| `docs/adr/")]
            if len(kept) != len(lines) - 1:
                raise HarnessError("expected exactly one docs/adr row in the overlay map")
            return "".join(kept)

        _edit_map(dest, edit)


STEPS: Dict[str, Callable[[Path], None]] = {"framework": add_framework, "gate": add_gate, "strip": strip_guidance}

EXPERIMENTS: Dict[str, Dict[str, Any]] = {
    "exp5": {
        "task": BUGFIX_TASK,
        "scorer": "bugfix",
        "arms": {"A": [], "P": ["framework"], "PG": ["framework", "gate"]},
        "rules_preloaded": {"P", "PG"},
    },
    "exp6": {
        "task": REFACTOR_TASK,
        "scorer": "refactor",
        # Order matters: strip runs after the overlay so it can drop the overlay's ADR map row.
        "arms": {"BD": [], "BS": ["strip"], "FD": ["framework"], "FS": ["framework", "strip"]},
        "rules_preloaded": {"FD", "FS"},
    },
}


def experiment(exp_id: str) -> Dict[str, Any]:
    if exp_id not in EXPERIMENTS:
        raise HarnessError(f"unknown experiment {exp_id!r}; known: {', '.join(EXPERIMENTS)}")
    return EXPERIMENTS[exp_id]


def build(exp_id: str, trial_id: str, arm: str, trials_dir: Path) -> Path:
    steps = experiment(exp_id)["arms"].get(arm)
    if steps is None:
        raise HarnessError(f"{exp_id} has no arm {arm!r}")
    dest = trials_dir / trial_id
    if dest.exists():
        raise HarnessError(f"{dest} already exists; a trial directory is never reused")
    shutil.copytree(FIXTURE, dest, ignore=IGNORE)
    for step in steps:
        STEPS[step](dest)
    return dest


# --------------------------------------------------------------------------------------
# Transcripts and the manipulation check
# --------------------------------------------------------------------------------------
def starting_context(transcript: Path) -> Tuple[List[str], List[str]]:
    """Attachment types and instruction files recorded before the first model turn."""
    kinds, sources = set(), []
    with open(transcript, encoding="utf-8") as handle:
        for line in handle:
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if rec.get("type") == "assistant":
                break
            if rec.get("type") != "attachment":
                continue
            att = rec.get("attachment") or {}
            kinds.add(str(att.get("type")))
            if att.get("type") == "instructions":
                files = att.get("files")
                if isinstance(files, list):  # Claude Code 2.1.304+: structured list
                    sources += [str(f.get("path")) for f in files if isinstance(f, dict)]
                else:  # older clients name the file only in the rendered text
                    text = "\n".join(str(c.get("content", "")) for c in (rec.get("rendered") or []) if isinstance(c, dict))
                    sources += re.findall(r"Contents of (.+?) \(", text)
    return sorted(kinds), sources


def manipulation_ok(expect_rules: bool, trial_dir: Path, kinds: Sequence[str], sources: Sequence[str]) -> Tuple[bool, str]:
    """Rules arms must load exactly their own CLAUDE.md; other arms must load no project instructions."""
    loaded = "instructions" in kinds
    if loaded != expect_rules:
        return False, f"instructions loaded={loaded}, expected {expect_rules}"
    norm = lambda p: os.path.normcase(os.path.normpath(str(p)))  # noqa: E731
    expected = [norm(trial_dir / "CLAUDE.md")] if expect_rules else []
    if sorted(norm(s) for s in sources) != expected:
        return False, f"instruction files {list(sources)}, expected {expected or 'none'}"
    return True, "ok"


def find_transcript(session_id: str, projects: Path = Path.home() / ".claude" / "projects") -> Optional[Path]:
    hits = list(projects.glob(f"*/{session_id}.jsonl"))
    return hits[0] if len(hits) == 1 else None


# --------------------------------------------------------------------------------------
# Running trials
# --------------------------------------------------------------------------------------
def clean_env() -> Dict[str, str]:
    """Drop the parent's Claude Code and Anthropic session variables so each child starts fresh."""
    env = {k: v for k, v in os.environ.items() if not (k.startswith("CLAUDE") or k.startswith("ANTHROPIC"))}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def load_log(log: Path) -> List[Dict[str, Any]]:
    if not log.is_file():
        return []
    return [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines() if line.strip()]


def schedule(exp_id: str, manifest: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Trial ids in pre-registered order: the arm plus its running count (A1, A2, ...)."""
    manifest = manifest or json.loads(MANIFEST.read_text(encoding="utf-8"))
    exp = next((e for e in manifest["experiments"] if e["id"] == exp_id), None)
    if exp is None or not exp.get("schedule"):
        raise HarnessError(f"{exp_id} is not pre-registered in {MANIFEST}")
    counts: Dict[str, int] = {}
    out = []
    for order, slot in enumerate(exp["schedule"], 1):
        counts[slot["arm"]] = counts.get(slot["arm"], 0) + 1
        out.append({"id": f"{slot['arm']}{counts[slot['arm']]}", "arm": slot["arm"], "order": order, "block": slot["block"]})
    return out


def run_trial(args: argparse.Namespace, exp_id: str, trial_id: str, arm: str, kind: str,
              order: Optional[int] = None, block: Optional[int] = None) -> Dict[str, Any]:
    exp = experiment(exp_id)
    root = Path(args.work) / exp_id
    trial_dir = build(exp_id, trial_id, arm, root / "trials")
    session_id = str(uuid.uuid4())
    prompt = INTRO.format(dir=trial_dir, py=args.python) + exp["task"]
    cmd = [args.claude, "-p", prompt, *CLAUDE_FLAGS, "--session-id", session_id]
    started = time.time()
    try:
        proc = subprocess.run(cmd, cwd=trial_dir, env=clean_env(), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=TIMEOUT_S)
        out, err, code = proc.stdout, proc.stderr, proc.returncode
    except subprocess.TimeoutExpired as exc:
        out, err, code = (exc.stdout or "") if isinstance(exc.stdout, str) else "", f"timeout after {TIMEOUT_S}s", -1
    wall_ms = round((time.time() - started) * 1000)
    try:
        result = json.loads(out)
    except ValueError:
        result = {"raw_stdout_tail": (out or "")[-2000:]}
    transcript = find_transcript(session_id)
    kinds, sources = starting_context(transcript) if transcript else ([], [])
    ok, why = manipulation_ok(arm in exp["rules_preloaded"], trial_dir, kinds, sources) if transcript else (False, "no transcript")
    keep = ("is_error", "subtype", "num_turns", "duration_ms", "total_cost_usd", "usage", "result", "raw_stdout_tail")
    entry = {
        "id": trial_id, "arm": arm, "kind": kind, "order": order, "block": block,
        "session_id": session_id, "dir": str(trial_dir), "transcript": str(transcript) if transcript else None,
        "exit_code": code, "wall_ms": wall_ms, "stderr_tail": (err or "")[-1500:],
        "result": {k: result[k] for k in keep if k in result},
        "starting_attachments": kinds, "instruction_sources": sources,
        "manipulation_check": {"ok": ok, "detail": why},
    }
    root.mkdir(parents=True, exist_ok=True)
    with open(root / "log.jsonl", "a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"{trial_id} [{arm}] exit={code} {wall_ms / 1000:.0f}s turns={entry['result'].get('num_turns')} "
          f"check={'OK' if ok else 'FAIL: ' + why}", flush=True)
    return entry


# --------------------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------------------
def walk(root: Path) -> Dict[str, Path]:
    out = {}
    for directory, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        for name in files:
            if name.endswith((".pyc", ".mgbak")):
                continue
            path = Path(directory) / name
            out[path.relative_to(root).as_posix()] = path
    return out


def diff_trees(trial: Path, reference: Path) -> Dict[str, List[str]]:
    a, b = walk(trial), walk(reference)
    return {
        "added": sorted(set(a) - set(b)),
        "removed": sorted(set(b) - set(a)),
        "modified": sorted(k for k in set(a) & set(b) if not filecmp.cmp(a[k], b[k], shallow=False)),
    }


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _pytest_counts(python: str, args: Sequence[str], cwd: Path, env: Optional[Dict[str, str]] = None) -> Tuple[int, int]:
    proc = subprocess.run([python, "-m", "pytest", "-q", "-p", "no:cacheprovider", *args], cwd=cwd,
                          env={**os.environ, **(env or {})}, capture_output=True, text=True, timeout=600)
    passed = int((re.search(r"(\d+) passed", proc.stdout) or [0, 0])[1])
    failed = int((re.search(r"(\d+) (?:failed|error)", proc.stdout) or [0, 0])[1])
    return passed, failed


def _opened(transcript: Path, needle: str) -> bool:
    for line in open(transcript, encoding="utf-8"):
        rec = json.loads(line)
        if rec.get("type") != "assistant":
            continue
        for block in rec["message"].get("content") or []:
            if isinstance(block, dict) and block.get("type") == "tool_use":
                inp = block.get("input") or {}
                if block["name"] == "Read" and needle in str(inp.get("file_path", "")):
                    return True
                command = str(inp.get("command", ""))
                if block["name"] in ("Bash", "PowerShell") and needle in command and not re.search(r"\b(grep|rg|Select-String)\b", command):
                    return True
    return False


def score_bugfix(python: str, trial: Path, reference: Path, transcript: Path) -> Dict[str, Any]:
    passed, failed = _pytest_counts(python, [str(BENCH / "acceptance_check.py")], REPO, {"BENCH_PROJECT": str(trial)})
    mg = subprocess.run([python, str(REPO / "scripts" / "mutation_guard.py"), "--test", "tests",
                         "--target", "shipdesk/shipping.py:qualifies_for_free_shipping",
                         "--runner", f'"{python}" -m pytest -x -q -p no:cacheprovider {{test}}',
                         "--cwd", str(trial), "--max-mutants", "0", "--min-score", "0", "--no-color", "--format", "json"],
                        cwd=trial, capture_output=True, text=True, timeout=900)
    try:
        data = json.loads(mg.stdout)
        mutation = f"{data['killed']}/{data['total']}"
    except (ValueError, KeyError):
        mutation = "ERROR"
    d = diff_trees(trial, reference)
    a, b = walk(trial), walk(reference)
    changed = d["added"] + d["modified"]
    e2e = any(_read(a[k]).count("compute_quote") > (_read(b[k]).count("compute_quote") if k in b else 0)
              for k in changed if k.startswith("tests/"))
    return {
        "acceptance": f"{passed}/{passed + failed}", "mutation": mutation, "e2e_test_added": e2e,
        "opened_legacy_module": _opened(transcript, "legacy_shipping"),
        "stray_changes": [k for k in changed + d["removed"] if k != "shipdesk/shipping.py" and not k.startswith("tests/")],
    }


def _tier_lines(root: Path) -> int:
    return sum(len(_read(p).splitlines()) for p in (root / "shipdesk" / "tiers").rglob("*.py"))


def score_refactor(python: str, trial: Path, reference: Path, transcript: Path) -> Dict[str, Any]:
    passed, failed = _pytest_counts(python, [str(BENCH / "tier_semantics_check.py")], REPO, {"BENCH_PROJECT": str(trial)})
    own_passed, own_failed = _pytest_counts(python, [], trial)
    d = diff_trees(trial, reference)
    changed = d["added"] + d["modified"] + d["removed"]
    ratio = round(_tier_lines(trial) / _tier_lines(reference), 3)
    return {
        "semantics": f"{passed}/{passed + failed}",
        "semantics_preserved": failed == 0 and passed == 11,
        "own_tests": f"{own_passed}/{own_passed + own_failed}",
        "tests_modified": [k for k in changed if k.startswith("tests/")],
        "tier_lines_ratio": ratio,
        "deduplicated": ratio <= 0.7,
        "stray_changes": [k for k in changed if not (k.startswith("shipdesk/tiers/") or k.startswith("tests/"))],
        "read_tier_spec": _opened(transcript, "tiers.md") or _opened(transcript, "docs/tiers"),
    }


SCORERS = {"bugfix": score_bugfix, "refactor": score_refactor}


def reference_copy(exp_id: str, arm: str, root: Path) -> Path:
    ref = root / "references" / arm
    if not ref.is_dir():
        build(exp_id, arm, arm, root / "references")
    return ref


# --------------------------------------------------------------------------------------
# Command line
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="bench.py", description="Run and score pre-registered benchmark experiments.")
    parser.add_argument("--work", default=os.environ.get("AI_BENCH_WORK") or str(Path(tempfile.gettempdir()) / "ai-context-mapping-bench"))
    parser.add_argument("--claude", default=os.environ.get("AI_BENCH_CLAUDE") or "claude")
    parser.add_argument("--python", default=os.environ.get("AI_BENCH_PYTHON") or sys.executable)
    parser.add_argument("command", choices=["status", "build", "pilot", "next", "score", "record"])
    parser.add_argument("experiment")
    parser.add_argument("rest", nargs="*")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        exp = experiment(args.experiment)
        root = Path(args.work) / args.experiment
        log = root / "log.jsonl"
        if args.command == "build":
            if len(args.rest) != 2:
                raise HarnessError("build needs TRIAL_ID ARM")
            print(build(args.experiment, args.rest[0], args.rest[1], root / "trials"))
            return 0
        if args.command == "pilot":
            done = {e["id"] for e in load_log(log)}
            for arm in args.rest or sorted(exp["arms"]):
                if f"pilot_{arm}" not in done:
                    run_trial(args, args.experiment, f"pilot_{arm}", arm, "pilot")
            return 0
        entries = load_log(log)
        trials = [e for e in entries if e["kind"] == "trial"]
        if args.command in ("status", "next"):
            if any(not e["manipulation_check"]["ok"] for e in trials):
                print("STOPPED: a trial failed its manipulation check (pre-registered stop rule). See", log)
                return 2
            plan = schedule(args.experiment)
            done = {e["id"] for e in trials}
            pending = [s for s in plan if s["id"] not in done]
            if args.command == "status":
                print(f"{args.experiment}: done {len(done)}/{len(plan)}; next: {' '.join(s['id'] for s in pending[:6]) or '-'}")
                return 0
            for slot in pending[: int(args.rest[0]) if args.rest else 1]:
                entry = run_trial(args, args.experiment, slot["id"], slot["arm"], "trial", slot["order"], slot["block"])
                if not entry["manipulation_check"]["ok"]:
                    print("STOPPED: manipulation check failed.")
                    return 2
            return 0
        if args.command == "score":
            scores = {}
            for e in trials:
                ref = reference_copy(args.experiment, e["arm"], root)
                scores[e["id"]] = SCORERS[exp["scorer"]](args.python, Path(e["dir"]), ref, Path(e["transcript"]))
                print(e["id"], json.dumps(scores[e["id"]]), flush=True)
            (root / "scores.json").write_text(json.dumps(scores, indent=1), encoding="utf-8")
            return 0
        if args.command == "record":
            return record(args.experiment, trials, root)
    except HarnessError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 2


def record(exp_id: str, trials: List[Dict[str, Any]], root: Path) -> int:
    """Write scored trials into the manifest (once); the scorer's output becomes each trial's ``scoring``."""
    scores = json.loads((root / "scores.json").read_text(encoding="utf-8"))
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    exp = next(e for e in manifest["experiments"] if e["id"] == exp_id)
    if exp.get("trials"):
        raise HarnessError(f"{exp_id} already has recorded trials")
    home = str(Path.home())
    rows = []
    for e in sorted(trials, key=lambda t: t["order"]):
        transcript = e["transcript"]
        if transcript.lower().startswith(home.lower()):
            transcript = "~" + transcript[len(home):].replace("\\", "/")
        rows.append({
            "id": e["id"], "arm": e["arm"], "agent_id": e["session_id"], "order": e["order"], "block": e["block"],
            "transcript": transcript,
            "harness": {"duration_ms": e["result"].get("duration_ms") or e["wall_ms"], "num_turns": e["result"].get("num_turns"),
                        "api_cost_usd": round(e["result"].get("total_cost_usd") or 0, 4), "exit_code": e["exit_code"]},
            "scoring": scores[e["id"]],
        })
    exp["trials"] = rows
    MANIFEST.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"recorded {len(rows)} trials for {exp_id}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
