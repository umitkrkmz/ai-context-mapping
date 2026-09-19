#!/usr/bin/env python3
"""Claude Code hook adapter that runs the invariant checker on edited Python files.

Claude Code passes a JSON description of each tool call on stdin. This adapter:

1. reads that JSON and ignores everything except Edit, Write, and MultiEdit calls on ``.py``
   files inside the project,
2. runs ``scripts/verify_invariants.py`` on the edited file, and
3. translates the result into the exit codes Claude Code understands.

It also answers one question for the commit gate in .claude/settings.json: "is this Bash call a
``git commit``?". Claude Code's own ``if`` filter runs a hook whenever it cannot resolve a
command (for example one that uses ``$(...)``), so the gate asks this script before it runs the
dependency budget and the map tests. Otherwise a failing check could block unrelated commands.

Exit codes (see the Claude Code hooks reference):
    0  nothing to report; Claude continues silently
    1  non-blocking problem, such as a broken rules file; shown to the user only
    2  invariant violation; stderr is fed back to Claude so it can repair the edit

``verify_invariants.py`` exits 1 on violations, which Claude Code would treat as a
non-blocking error that Claude never sees. Mapping 1 to 2 here is the whole reason for this file.

The checker is loaded with ``importlib`` and called in-process, so this file needs no
``subprocess`` (invariant NI-002) and no third-party packages (invariant NI-001).

Usage (normally invoked by .claude/settings.json):
    python .claude/hooks/guardrail_hook.py post-edit               read the hook JSON from stdin
    python .claude/hooks/guardrail_hook.py post-edit --file PATH   check one file by hand
    python .claude/hooks/guardrail_hook.py is-git-commit           exit 0 if stdin is a git commit
"""
from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import os
import re
import sys
from pathlib import Path
from types import ModuleType
from typing import Any, Dict, Optional, Sequence

EDIT_TOOLS = ("Edit", "Write", "MultiEdit")
VERIFIER_RELATIVE_PATH = Path("scripts") / "verify_invariants.py"
GIT_COMMIT = re.compile(
    r"\bgit(?:\s+(?:-C|-c|--git-dir|--work-tree)\s+\S+|\s+--?[\w-]+(?:=\S+)?)*\s+commit(?![\w-])"
)


def project_root(payload: Dict[str, Any]) -> Path:
    """Locate the project root from the environment, the hook payload, or the working directory."""
    chosen = os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(str(chosen)).resolve()


def load_verifier(root: Path) -> Optional[ModuleType]:
    """Import scripts/verify_invariants.py by path; return None when the project lacks it."""
    path = root / VERIFIER_RELATIVE_PATH
    if not path.is_file():
        return None
    spec = importlib.util.spec_from_file_location("verify_invariants", path)
    if spec is None or spec.loader is None:
        return None
    module = importlib.util.module_from_spec(spec)
    sys.modules["verify_invariants"] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module


def edited_python_file(payload: Dict[str, Any], root: Path) -> Optional[Path]:
    """Return the edited ``.py`` file inside ``root``, or None when the call is not relevant."""
    if payload.get("tool_name") not in EDIT_TOOLS:
        return None
    tool_input = payload.get("tool_input")
    raw = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw.endswith(".py"):
        return None
    candidate = Path(raw)
    target = (candidate if candidate.is_absolute() else root / candidate).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        return None
    return target if target.is_file() else None


def is_git_commit(payload: Dict[str, Any]) -> bool:
    """True when the payload is a Bash call that runs ``git commit`` (global git options allowed)."""
    if payload.get("tool_name") != "Bash":
        return False
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    return isinstance(command, str) and GIT_COMMIT.search(command) is not None


def check_file(root: Path, target: Path) -> int:
    """Run the invariant checker on one file and return a Claude Code exit code."""
    verifier = load_verifier(root)
    if verifier is None:
        return 0
    relative = target.relative_to(root).as_posix()
    captured = io.StringIO()
    try:
        with contextlib.redirect_stdout(captured), contextlib.redirect_stderr(captured):
            status = verifier.main(["--root", str(root), "--no-color", relative])
    except SystemExit as exc:
        status = exc.code if isinstance(exc.code, int) else 2
    report = captured.getvalue().strip()
    if status == 0:
        return 0
    if status == 1:
        print(f"Invariant violation after editing {relative}.", file=sys.stderr)
        print("Fix the code. Do not delete rules or INVARIANT markers to make the check pass.", file=sys.stderr)
        print(report, file=sys.stderr)
        return 2
    print(f"The invariant checker could not run (exit {status}):", file=sys.stderr)
    print(report, file=sys.stderr)
    return 1


def read_payload() -> Dict[str, Any]:
    """Decode the hook JSON from stdin; an empty or invalid payload becomes an empty dict."""
    try:
        decoded = json.load(sys.stdin)
    except ValueError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="guardrail_hook.py",
        description="Claude Code hook adapter for the AI guardrails.",
        epilog="exit codes: 0 ok, 1 non-blocking problem, 2 violation (blocks / feeds back to Claude)",
    )
    parser.add_argument(
        "mode",
        choices=("post-edit", "is-git-commit"),
        help="'post-edit' checks a file Claude just edited; 'is-git-commit' exits 0 only for a git commit",
    )
    parser.add_argument("--file", help="check this file directly instead of reading the hook JSON from stdin")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    if args.mode == "is-git-commit":
        return 0 if is_git_commit(read_payload()) else 1
    if args.file:
        payload: Dict[str, Any] = {"tool_name": "Edit", "tool_input": {"file_path": args.file}}
    else:
        payload = read_payload()
    root = project_root(payload)
    target = edited_python_file(payload, root)
    if target is None:
        return 0
    return check_file(root, target)


if __name__ == "__main__":
    sys.exit(main())
