#!/usr/bin/env python3
"""Claude Code PreToolUse gate that enforces Rule 1: read the project map before you search.

AGENTS.md Rule 1 says "read maps/project-map.md before running exploratory grep or find". In our
v1.0.2 benchmark no agent followed it (0 of 3): every one grepped first. An instruction that is
ignored is not a guardrail, so this hook turns the rule into a gate.

Until the map has been inspected in the current session, the hook blocks (exit code 2):

* the ``Grep`` and ``Glob`` tools,
* exploratory shell commands: ``grep -r``, ``grep PATTERN path``, ``rg``, ``ag``, ``ack``, ``find``,
  ``fd``, ``tree``, ``ls -R``, ``git grep``, and their PowerShell equivalents.

It always allows everything else, including ``git status``, running tests, editing and writing files,
and pipeline filters such as ``pytest | grep passed`` (a filter over a pipe is not a repository search).

The map counts as "inspected" when the agent:

* reads ``maps/project-map.md`` with the Read tool,
* runs ``cat``, ``head``, ``sed``, ``Get-Content`` and similar on it, or greps that one file,
* runs ``python mcp/context_server.py --call read_project_map`` (or ``get_file_purpose``), or
* calls the MCP tools ``read_project_map`` or ``get_file_purpose``.

State is one small marker file per (session, agent) in the system temp directory, never in the
repository, so it cannot affect the map-coverage test. A sub-agent has its own scope: a parent that
read the map does not unlock a sub-agent that has not.

Fail-open by design (invariant NI-010): if the project has no map, the payload is malformed, or anything
unexpected happens, the call is allowed. Set ``AI_GUARDRAILS_PERMISSIVE=1`` to disable the gate for
manual or CI runs, or ``AI_GUARDRAILS_ANY_MAP=1`` to let a nested project's own map count as well
(monorepos, benchmark harnesses). This is a guardrail against a reflex, not a security boundary: a
determined agent can route around a shell heuristic.

Exit codes (see the Claude Code hooks reference): 0 allow, 2 block (stderr is fed back to Claude).

Usage (normally invoked by .claude/settings.json):
    python .claude/hooks/map_gate.py            read the hook JSON from stdin
    python .claude/hooks/map_gate.py --status   show whether this project's markers exist
    python .claude/hooks/map_gate.py --reset    delete this project's markers (start locked again)

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence, TextIO, Tuple

MAP_RELATIVE = "maps/project-map.md"
PERMISSIVE_ENV = "AI_GUARDRAILS_PERMISSIVE"  # INVARIANT(NI-010): keep the bypass for manual and CI runs.
STATE_DIR_ENV = "AI_GUARDRAILS_STATE_DIR"
ANY_MAP_ENV = "AI_GUARDRAILS_ANY_MAP"  # opt in: a nested project's own maps/project-map.md counts too
STATE_TTL_SECONDS = 7 * 24 * 3600
BLOCK_MESSAGE = (
    "Rule 1 Enforced: Access denied. You must inspect 'maps/project-map.md' or query the MCP context "
    "server before running broad repository searches or grepping."
)
HINT = (
    "Next step: read maps/project-map.md with the Read tool (or run: python mcp/context_server.py "
    "--call read_project_map), then repeat your search. The map names the file you need."
)

READ_TOOLS = {"Read", "FileRead", "View"}
SEARCH_TOOLS = {"Grep", "Glob"}
SHELL_TOOLS = {"Bash", "PowerShell"}
MCP_MAP_TOOLS = ("read_project_map", "get_file_purpose")

GREP_LIKE = {"grep", "egrep", "fgrep", "zgrep"}
RG_LIKE = {"rg", "ag", "ack", "ack-grep"}
FIND_LIKE = {"find", "fd", "fdfind", "tree"}
READERS = {"cat", "head", "tail", "less", "more", "sed", "awk", "bat", "nl", "type", "cut", "sort", "get-content", "gc"}
WRAPPERS = {"sudo", "time", "nice", "command", "builtin", "exec", "nohup", "env", "xargs"}
POWERSHELL_SEARCH = {"select-string", "sls"}
POWERSHELL_LISTERS = {"get-childitem", "gci", "ls", "dir"}
# Options that consume the next token, per short letter and long name.
SHORT_VALUE_LETTERS = set("efABCmdDgtTjEMX")
LONG_VALUE_OPTIONS = {
    "--regexp", "--file", "--max-count", "--context", "--after-context", "--before-context", "--include",
    "--exclude", "--exclude-dir", "--glob", "--iglob", "--type", "--type-not", "--threads", "--max-depth",
}


# --------------------------------------------------------------------------------------
# Shell command analysis
# --------------------------------------------------------------------------------------
def split_segments(command: str) -> List[Tuple[str, bool]]:
    """Split a shell command on unquoted ``;``, ``&&``, ``||``, ``|`` and newlines.

    Returns ``(segment, piped)`` pairs, where ``piped`` is True when the segment reads a pipe.
    """
    segments: List[Tuple[str, bool]] = []
    current: List[str] = []
    quote = ""
    piped_next = False
    i = 0
    while i < len(command):
        char = command[i]
        if quote:
            current.append(char)
            if char == "\\" and quote == '"' and i + 1 < len(command):
                current.append(command[i + 1])
                i += 1
            elif char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char == "\\" and i + 1 < len(command):
            current.append(char)
            current.append(command[i + 1])
            i += 1
        elif char in ";\n" or command[i:i + 2] in ("&&", "||") or char == "|":
            width = 2 if command[i:i + 2] in ("&&", "||") else 1
            text = "".join(current).strip()
            if text:
                segments.append((text, piped_next))
            piped_next = char == "|" and width == 1
            current = []
            i += width
            continue
        else:
            current.append(char)
        i += 1
    text = "".join(current).strip()
    if text:
        segments.append((text, piped_next))
    return segments


def tokenize(segment: str, shell: str) -> List[str]:
    """Split one segment into words, tolerating unbalanced quotes."""
    try:
        words = shlex.split(segment, posix=(shell != "PowerShell"))
    except ValueError:
        words = segment.split()
    return [w[1:-1] if len(w) >= 2 and w[0] == w[-1] and w[0] in "\"'" else w for w in words]


def program_and_args(words: Sequence[str]) -> Tuple[str, List[str]]:
    """Drop ``VAR=value`` prefixes and wrapper commands, then return ``(program, args)``."""
    index = 0
    while index < len(words):
        word = words[index]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", word) or word.lower() in WRAPPERS:
            index += 1
            continue
        break
    if index >= len(words):
        return "", []
    name = os.path.basename(words[index].replace("\\", "/")).lower()
    if name.endswith(".exe"):
        name = name[:-4]
    return name, list(words[index + 1:])


def parse_operands(args: Sequence[str]) -> Tuple[List[str], bool, bool]:
    """Return ``(operands, recursive_flag, pattern_given_by_option)`` for grep-like argument lists."""
    operands: List[str] = []
    recursive = False
    pattern_given = False
    index = 0
    only_operands = False
    while index < len(args):
        token = args[index]
        index += 1
        if only_operands or not token.startswith("-") or token == "-":
            operands.append(token)
            continue
        if token == "--":
            only_operands = True
            continue
        if token.startswith("--"):
            name = token.split("=", 1)[0]
            if name in ("--recursive", "--dereference-recursive"):
                recursive = True
            if name in ("--regexp", "--file"):
                pattern_given = True
            if "=" not in token and name in LONG_VALUE_OPTIONS:
                index += 1
            continue
        letters = token[1:]
        for position, letter in enumerate(letters):
            if letter in "rR":
                recursive = True
            if letter in SHORT_VALUE_LETTERS:
                if letter in "ef":
                    pattern_given = True
                if position == len(letters) - 1:
                    index += 1  # the value is the next token
                break
    return operands, recursive, pattern_given


def _git_subcommand(args: Sequence[str]) -> str:
    index = 0
    while index < len(args):
        token = args[index]
        if token in ("-C", "-c", "--git-dir", "--work-tree", "--namespace"):
            index += 2
            continue
        if token.startswith("-"):
            index += 1
            continue
        return token
    return ""


def is_search(program: str, args: Sequence[str], piped: bool, shell: str) -> bool:
    """True when the command explores the repository (as opposed to filtering a pipe)."""
    lowered = [a.lower() for a in args]
    if shell == "PowerShell" and program in POWERSHELL_SEARCH:
        has_path = any(a in ("-path", "-literalpath") for a in lowered)
        return has_path or "-recurse" in lowered or not piped
    if shell == "PowerShell" and program in POWERSHELL_LISTERS:
        return "-recurse" in lowered or "-r" in lowered or "/s" in lowered
    if program in FIND_LIKE:
        return True
    if program == "ls":
        return any(a == "--recursive" or re.match(r"^-[A-Za-z]*R[A-Za-z]*$", a) for a in args)
    if program == "git":
        return _git_subcommand(args) == "grep"
    if program in GREP_LIKE:
        operands, recursive, pattern_given = parse_operands(args)
        paths = operands if pattern_given else operands[1:]
        return recursive or bool(paths)
    if program in RG_LIKE:
        operands, _recursive, pattern_given = parse_operands(args)
        paths = operands if pattern_given else operands[1:]
        return bool(paths) or not piped
    return False


def _norm(path: str) -> str:
    return os.path.normcase(os.path.normpath(path.replace("\\", "/"))).replace("\\", "/")


def is_map_file(path: str, root: Path, any_map: bool = False) -> bool:
    """True when ``path`` (absolute or relative to the project root) is maps/project-map.md.

    With ``any_map`` (env AI_GUARDRAILS_ANY_MAP=1) an existing ``maps/project-map.md`` belonging to a
    nested project also counts. That suits monorepos and benchmark harnesses, where the project an agent
    works in is not the project whose hooks are running. It is off by default.
    """
    if not path:
        return False
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = root / candidate
    try:
        resolved = os.path.realpath(candidate)
        expected = os.path.realpath(root / MAP_RELATIVE)
    except OSError:
        return False
    if os.path.normcase(resolved) == os.path.normcase(expected):
        return True
    return any_map and resolved.replace("\\", "/").lower().endswith("/" + MAP_RELATIVE) and os.path.isfile(resolved)


def references_map(program: str, args: Sequence[str], root: Path, piped: bool, any_map: bool = False) -> bool:
    """True when a command inspects the project map (reads it, or asks the MCP server for it)."""
    if program in READERS:
        return any(is_map_file(a, root, any_map) for a in args if not a.startswith("-"))
    if program in GREP_LIKE or program in RG_LIKE:
        operands, _recursive, pattern_given = parse_operands(args)
        paths = operands if pattern_given else operands[1:]
        return bool(paths) and all(is_map_file(p, root, any_map) for p in paths)
    if program.startswith("python") or program == "py":
        text = " ".join(args).replace("\\", "/")
        return "context_server.py" in text and any(f"--call {name}" in text or f"--call={name}" in text for name in MCP_MAP_TOOLS)
    return False


def classify_shell(command: str, root: Path, shell: str = "Bash", any_map: bool = False) -> str:
    """Classify a shell command as ``"map"`` (inspects the map), ``"search"``, or ``"other"``.

    Segments are examined in order, so ``cat maps/project-map.md && grep -r x .`` is a map access.
    """
    for segment, piped in split_segments(command):
        program, args = program_and_args(tokenize(segment, shell))
        if not program:
            continue
        if references_map(program, args, root, piped, any_map):
            return "map"
        if is_search(program, args, piped, shell):
            return "search"
    return "other"


# --------------------------------------------------------------------------------------
# State: one marker file per (session, agent) in the temp directory
# --------------------------------------------------------------------------------------
def state_dir(root: Path, env: Mapping[str, str]) -> Path:
    override = env.get(STATE_DIR_ENV)
    if override:
        return Path(override)
    digest = hashlib.sha1(os.path.normcase(str(root)).encode("utf-8")).hexdigest()[:12]
    return Path(tempfile.gettempdir()) / f"ai-guardrails-{digest}"


def scope_of(payload: Mapping[str, Any]) -> Tuple[str, str]:
    session = payload.get("session_id")
    agent = payload.get("agent_id")
    return (str(session) if session else "no-session", str(agent) if agent else "main")


def marker_path(root: Path, payload: Mapping[str, Any], env: Mapping[str, str]) -> Path:
    session, agent = scope_of(payload)
    key = hashlib.sha1(f"{session}|{agent}".encode("utf-8")).hexdigest()[:16]
    return state_dir(root, env) / f"map-read-{key}.json"


def is_unlocked(root: Path, payload: Mapping[str, Any], env: Mapping[str, str]) -> bool:
    return marker_path(root, payload, env).is_file()


def mark_unlocked(root: Path, payload: Mapping[str, Any], env: Mapping[str, str], via: str) -> None:
    """Record that the map was inspected; also prune markers older than the retention period."""
    path = marker_path(root, payload, env)
    session, agent = scope_of(payload)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"session": session, "agent": agent, "via": via, "time": int(time.time())}), encoding="utf-8")
        cutoff = time.time() - STATE_TTL_SECONDS
        for old in path.parent.glob("map-read-*.json"):
            if old != path and old.stat().st_mtime < cutoff:
                old.unlink()
    except OSError:
        pass  # fail open: without a writable state directory the gate simply stays out of the way


# --------------------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------------------
def project_root(payload: Mapping[str, Any], env: Mapping[str, str]) -> Path:
    chosen = env.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or os.getcwd()
    return Path(str(chosen)).resolve()


def tool_action(payload: Mapping[str, Any], root: Path, any_map: bool = False) -> Tuple[str, str]:
    """Decide what a tool call is: ``("map", via)``, ``("search", why)``, or ``("other", "")``."""
    name = str(payload.get("tool_name") or "")
    tool_input = payload.get("tool_input")
    tool_input = tool_input if isinstance(tool_input, dict) else {}
    if name.startswith("mcp__") and name.rsplit("__", 1)[-1] in MCP_MAP_TOOLS:
        return "map", f"mcp:{name}"
    if name in READ_TOOLS:
        return ("map", "Read") if is_map_file(str(tool_input.get("file_path") or ""), root, any_map) else ("other", "")
    if name == "Grep":
        return ("map", "Grep") if is_map_file(str(tool_input.get("path") or ""), root, any_map) else ("search", "Grep")
    if name == "Glob":
        pattern = str(tool_input.get("pattern") or "")
        literal = not any(ch in pattern for ch in "*?[{")
        return ("map", "Glob") if literal and is_map_file(pattern, root, any_map) else ("search", "Glob")
    if name in SHELL_TOOLS:
        command = str(tool_input.get("command") or "")
        kind = classify_shell(command, root, name, any_map)
        return (kind, f"{name}: {command[:60]}") if kind != "other" else ("other", "")
    return "other", ""


def gate(payload: Mapping[str, Any], env: Optional[Mapping[str, str]] = None) -> Tuple[int, str]:
    """Return ``(exit_code, stderr_message)`` for one PreToolUse payload."""
    env = os.environ if env is None else env
    if env.get(PERMISSIVE_ENV) == "1":
        return 0, ""
    root = project_root(payload, env)
    if not (root / MAP_RELATIVE).is_file():
        return 0, ""  # INVARIANT(NI-010): no map means nothing to enforce; fail open.
    action, detail = tool_action(payload, root, env.get(ANY_MAP_ENV) == "1")
    if action == "map":
        mark_unlocked(root, payload, env, detail)
        return 0, ""
    if action == "search" and not is_unlocked(root, payload, env):
        return 2, f"{BLOCK_MESSAGE}\n{HINT}"
    return 0, ""


def read_payload(stream: TextIO) -> Dict[str, Any]:
    try:
        decoded = json.load(stream)
    except ValueError:
        return {}
    return decoded if isinstance(decoded, dict) else {}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="map_gate.py",
        description="Claude Code PreToolUse gate: block searches until maps/project-map.md has been read.",
        epilog="exit codes: 0 allow, 2 block (the message on stderr is fed back to Claude)",
    )
    parser.add_argument("--status", action="store_true", help="show this project's marker directory and files, then exit")
    parser.add_argument("--reset", action="store_true", help="delete this project's markers so the gate is locked again")
    return parser


def main(argv: Optional[Sequence[str]] = None, stdin: Optional[TextIO] = None, stderr: Optional[TextIO] = None) -> int:
    args = build_parser().parse_args(argv)
    out = stderr if stderr is not None else sys.stderr
    env = os.environ
    if args.status or args.reset:
        directory = state_dir(project_root({}, env), env)
        markers = sorted(directory.glob("map-read-*.json")) if directory.is_dir() else []
        if args.reset:
            for marker in markers:
                marker.unlink()
        print(f"state directory: {directory}")
        print(f"markers: {0 if args.reset else len(markers)}" + (f" (removed {len(markers)})" if args.reset else ""))
        return 0
    try:
        code, message = gate(read_payload(stdin if stdin is not None else sys.stdin), env)
    except Exception:  # noqa: BLE001 - a broken gate must never block the agent
        return 0
    if message:
        print(message, file=out)
    return code


if __name__ == "__main__":
    sys.exit(main())
