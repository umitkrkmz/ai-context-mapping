#!/usr/bin/env python3
"""Standalone Model Context Protocol server that serves the project map to AI clients.

Transport: JSON-RPC 2.0 over stdio, one JSON message per line (the MCP stdio transport).
No third-party packages are needed, so the file can be copied into any project on its own.

Tools exposed to Claude Desktop, Cursor, and other MCP clients:

    read_project_map()                  Return the full content of maps/project-map.md.
    get_file_purpose(file_path)         Return the category, purpose, and invariants for one path.
    get_invariants_for_file(file_path)  Return every invariant that covers a path: rules whose scope
                                        matches it, IDs its map row lists, and project-wide decisions.
    check_map()                         Report paths missing from the map, stale rows, and rows whose
                                        description is still a placeholder.

Every tool only reads. Running the checks (verify_invariants.py, the dependency budget, the mutation
guard) stays with the hooks, the pre-commit hook, and CI: the server spawns no process (invariant NI-002)
and imports nothing from scripts/ (NI-003), so it repeats the little matching logic it needs. The tests
keep that logic in step with the scripts.

The server reads the project's files on every call, so edits show up without a restart.

Usage:
    python mcp/context_server.py                          run as an MCP stdio server
    python mcp/context_server.py --root /path/to/project  serve a different project
    python mcp/context_server.py --check                  validate the map and exit
    python mcp/context_server.py --call get_file_purpose --arg file_path=AGENTS.md

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import difflib
import json
import os
import posixpath
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

SERVER_NAME = "ai-context-mapping"
SERVER_VERSION = "1.1.0"
SUPPORTED_PROTOCOLS = ("2025-06-18", "2025-03-26", "2024-11-05")
MAP_RELATIVE_PATH = "maps/project-map.md"
INVARIANTS_DOC = "invariants/negative-invariants.md"
DECISIONS_DIR = "decisions"
FILE_INDEX_TITLE = "file index"

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

TOOLS: List[Dict[str, Any]] = [
    {
        "name": "read_project_map",
        "description": (
            "Return the full content of maps/project-map.md: every file and directory with its "
            "category, purpose, and protecting invariants. Call this before running exploratory "
            "grep or find commands."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "name": "get_file_purpose",
        "description": (
            "Return the purpose, category, and invariants for one file or directory listed in the "
            "project map. Use it to decide whether a file is worth opening and which invariants "
            "apply before editing it."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path relative to the project root, for example 'scripts/mutation_guard.py'.",
                }
            },
            "required": ["file_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "get_invariants_for_file",
        "description": (
            "List every invariant that protects one path before you edit it: machine-checked rules whose "
            "scope covers the path (even when its map row lists none), the IDs its map row lists, and the "
            "project-wide decision records. Includes each invariant's 'Never' and 'Safe alternatives' notes."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path relative to the project root, for example 'src/billing/tiers.py'.",
                }
            },
            "required": ["file_path"],
            "additionalProperties": False,
        },
    },
    {
        "name": "check_map",
        "description": (
            "Check whether maps/project-map.md is current: paths with no row, rows whose path no longer "
            "exists, and rows whose description is still a placeholder. Read-only; it does not fix anything."
        ),
        "inputSchema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
]


def log(message: str) -> None:
    """Write diagnostics to stderr; stdout is reserved for protocol messages."""
    if os.environ.get("AI_CONTEXT_DEBUG"):
        print(f"[context_server] {message}", file=sys.stderr, flush=True)


class ToolError(Exception):
    """A tool ran but could not produce a result (reported with ``isError: true``)."""


class InvalidParams(Exception):
    """The caller sent malformed arguments (reported as a JSON-RPC error)."""


# --------------------------------------------------------------------------------------
# Map parsing
# --------------------------------------------------------------------------------------
@dataclass
class Row:
    path: str
    category: str
    purpose: str
    invariants: str


_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
_PATH_CELL = re.compile(r"^`([^`]+)`$")
_ID_PATTERN = re.compile(r"\b[A-Z]{2,5}-\d{1,4}\b")


def _split_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.strip().replace("\\|", "|") for cell in _UNESCAPED_PIPE.split(stripped)]


def parse_file_index(text: str) -> Dict[str, Row]:
    """Parse the table under the ``## File Index`` heading into rows keyed by path."""
    rows: Dict[str, Row] = {}
    in_index = False
    for line in text.splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            in_index = heading.group(1).lower().startswith(FILE_INDEX_TITLE)
            continue
        if not in_index or not line.lstrip().startswith("|"):
            continue
        cells = _split_row(line)
        if len(cells) < 4:
            continue
        match = _PATH_CELL.match(cells[0])
        if match:
            rows[match.group(1)] = Row(match.group(1), cells[1], cells[2], cells[3])
    return rows


# --------------------------------------------------------------------------------------
# Invariant lookup
# --------------------------------------------------------------------------------------
_FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)\s*$")


_SECTION_HEADING = re.compile(r"^###\s+([A-Z]{2,5}-\d{1,4})\s*[:\-]\s*(.+?)\s*$")


def _split_fences(text: str) -> Tuple[List[Tuple[str, List[str]]], List[Tuple[int, str]]]:
    """Return ``(fenced blocks as (info, lines), lines outside any fence as (line_no, text))``."""
    blocks: List[Tuple[str, List[str]]] = []
    outside: List[Tuple[int, str]] = []
    fence: Optional[Tuple[str, int, str]] = None
    body: List[str] = []
    for number, line in enumerate(text.splitlines()):
        match = _FENCE_LINE.match(line)
        if fence is None:
            if match:
                fence = (match.group(1)[0], len(match.group(1)), match.group(2))
                body = []
            else:
                outside.append((number, line))
            continue
        char, length, info = fence
        if match and match.group(1)[0] == char and len(match.group(1)) >= length and not match.group(2):
            blocks.append((info, body))
            fence = None
        else:
            body.append(line)
    return blocks, outside


def _rule_blocks(text: str) -> List[Dict[str, Any]]:
    """Decode the top-level ``invariant-rule`` fenced blocks; malformed ones are skipped."""
    rules: List[Dict[str, Any]] = []
    for info, body in _split_fences(text)[0]:
        if info != "invariant-rule":
            continue
        try:
            decoded = json.loads("\n".join(body))
        except ValueError:
            continue
        for item in decoded if isinstance(decoded, list) else [decoded]:
            if isinstance(item, dict) and isinstance(item.get("id"), str):
                rules.append(item)
    return rules


def _rule_descriptions(text: str) -> Dict[str, str]:
    """Extract ``id -> description`` from top-level ``invariant-rule`` fenced blocks."""
    return {rule["id"]: str(rule.get("description", "")).strip() for rule in _rule_blocks(text)}


def _narratives(text: str) -> Dict[str, Tuple[str, List[str]]]:
    """Map each ``### ID: title`` section to its title and prose lines (fenced blocks left out)."""
    found: Dict[str, Tuple[str, List[str]]] = {}
    current: Optional[str] = None
    for _number, line in _split_fences(text)[1]:
        heading = _SECTION_HEADING.match(line)
        if heading:
            current = heading.group(1)
            found[current] = (heading.group(2), [])
        elif line.startswith("#"):
            current = None
        elif current is not None and line.strip():
            found[current][1].append(line.rstrip())
    return found


_GLOB_CACHE: Dict[str, "re.Pattern[str]"] = {}


def _glob_regex(pattern: str) -> "re.Pattern[str]":
    """Same glob semantics as scripts/verify_invariants.py: ``**`` any depth, ``*`` and ``?`` in one segment."""
    cached = _GLOB_CACHE.get(pattern)
    if cached is not None:
        return cached
    out: List[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if pattern[i:i + 2] == "**":
                i += 2
                if pattern[i:i + 1] == "/":
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(char))
        i += 1
    compiled = re.compile("^" + "".join(out) + "$")
    _GLOB_CACHE[pattern] = compiled
    return compiled


def _matches_any(path: str, patterns: Any) -> bool:
    if isinstance(patterns, str):
        patterns = [patterns]
    return isinstance(patterns, list) and any(isinstance(p, str) and _glob_regex(p).match(path) for p in patterns)


def rule_covers(rule: Dict[str, Any], path: str) -> bool:
    """True when ``verify_invariants.py`` would check ``path`` against ``rule``."""
    if rule.get("type") == "required-text":
        return rule.get("file") == path
    return _matches_any(path, rule.get("scope", ["**/*.py"])) and not _matches_any(path, rule.get("exclude", []))


def rule_detail(rule: Dict[str, Any], path: str) -> str:
    """One line on what the rule demands of this particular path."""
    kind = rule.get("type")
    if kind == "required-text":
        return "this file must keep: " + ", ".join(repr(t) for t in rule.get("contains", []))
    if kind == "isolated-import":
        modules = ", ".join(rule.get("modules", []))
        if _matches_any(path, rule.get("allowed_in", [])):
            return f"this file is the one place allowed to import {modules}"
        return f"do not import {modules} here; use {rule.get('use') or ', '.join(rule.get('allowed_in', []))}"
    if kind in ("forbidden-import", "forbidden-call") and _matches_any(path, rule.get("allow_in", [])):
        return "this file is exempt (allow_in)"
    if kind == "forbidden-import":
        return "must not import: " + ", ".join(rule.get("forbidden", []))
    if kind == "forbidden-call":
        return "must not call: " + ", ".join(rule.get("calls", []))
    if kind == "stdlib-only":
        allowed = rule.get("allow", [])
        return "standard library only" + (f" (also allowed: {', '.join(allowed)})" if allowed else "")
    return f"rule type {kind}"


# --------------------------------------------------------------------------------------
# Map freshness (same semantics as scripts/init_mapping.py --check; NI-003 keeps them separate)
# --------------------------------------------------------------------------------------
ALWAYS_IGNORED = (".git/", "__pycache__/", ".pytest_cache/")
IGNORE_FILES = (".agentignore", ".git/info/exclude")
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|describe manually", re.IGNORECASE)


def _ignore_glob(pattern: str) -> str:
    """Translate one gitignore-style glob (with ``[...]`` classes) into a regex fragment."""
    out: List[str] = []
    i = 0
    while i < len(pattern):
        char = pattern[i]
        if char == "*":
            if pattern[i:i + 2] == "**":
                i += 2
                if pattern[i:i + 1] == "/":
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
                continue
            out.append("[^/]*")
        elif char == "?":
            out.append("[^/]")
        elif char == "[":
            end = pattern.find("]", i + 1)
            if end == -1:
                out.append(re.escape(char))
            else:
                body = pattern[i + 1:end]
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body.replace("\\", "\\\\") + "]")
                i = end
        else:
            out.append(re.escape(char))
        i += 1
    return "".join(out)


class IgnoreRules:
    """``.agentignore`` and ``.git/info/exclude`` rules, evaluated like scripts/init_mapping.py."""

    def __init__(self, root: Path) -> None:
        patterns = list(ALWAYS_IGNORED)
        for name in IGNORE_FILES:
            candidate = root / name
            if candidate.is_file():
                patterns.extend(candidate.read_text(encoding="utf-8", errors="replace").splitlines())
        self._rules: List[Tuple["re.Pattern[str]", bool, bool]] = []
        for raw in patterns:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            negate = line.startswith("!")
            if negate:
                line = line[1:]
            dir_only = line.endswith("/")
            line = line.rstrip("/")
            if not line:
                continue
            anchored = line.startswith("/") or "/" in line
            body = _ignore_glob(line.lstrip("/"))
            self._rules.append((re.compile(f"^{body}$" if anchored else f"^(?:.*/)?{body}$"), negate, dir_only))

    def _verdict(self, rel_path: str, is_dir: bool) -> Optional[bool]:
        verdict: Optional[bool] = None
        for regex, negate, dir_only in self._rules:
            if (is_dir or not dir_only) and regex.match(rel_path):
                verdict = not negate
        return verdict

    def ignored(self, rel_path: str, is_dir: bool) -> bool:
        """True if the path, or any parent directory, is ignored."""
        parts = rel_path.strip("/").split("/")
        for depth in range(1, len(parts) + 1):
            if self._verdict("/".join(parts[:depth]), is_dir if depth == len(parts) else True):
                return True
        return False


def scan_paths(root: Path) -> List[str]:
    """Every non-ignored file and directory (directories end with ``/``), as the map must list them."""
    rules = IgnoreRules(root)
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        prefix = "" if rel_dir == "." else rel_dir + "/"
        kept: List[str] = []
        for name in sorted(dirnames):
            rel = prefix + name
            if rules.ignored(rel, True):
                continue
            if os.path.islink(os.path.join(dirpath, name)):
                found.append(rel)
                continue
            kept.append(name)
            found.append(rel + "/")
        dirnames[:] = kept
        found.extend(prefix + name for name in sorted(filenames) if not rules.ignored(prefix + name, False))
    return found


def map_diff(paths: Sequence[str], rows: Dict[str, Row]) -> Tuple[List[str], List[str]]:
    """Return ``(missing, stale)`` like ``init_mapping.py --check``; ``dir/**`` rows cover their subtree."""
    groups = [key[:-2] for key in rows if key.endswith("/**")]
    missing = [p for p in paths if p not in rows and not any(p.startswith(g) for g in groups)]
    actual = set(paths)
    stale = sorted(key for key in rows if (key[:-2] if key.endswith("/**") else key) not in actual)
    return missing, stale


def load_invariant_index(root: Path) -> Dict[str, str]:
    """Map invariant and decision IDs to one-line descriptions."""
    index: Dict[str, str] = {}
    doc = root / INVARIANTS_DOC
    if doc.is_file():
        text = doc.read_text(encoding="utf-8", errors="replace")
        rules = _rule_descriptions(text)
        for match in re.finditer(r"^###\s+([A-Z]{2,5}-\d{1,4})\s*[:\-]\s*(.+?)\s*$", text, re.M):
            title = match.group(2)
            detail = rules.get(match.group(1), "")
            index[match.group(1)] = f"{title} - {detail}" if detail and detail != title else title
        for rule_id, description in rules.items():
            index.setdefault(rule_id, description)
    decisions = root / DECISIONS_DIR
    if decisions.is_dir():
        for path in sorted(list(decisions.glob("*.yaml")) + list(decisions.glob("*.yml"))):
            text = path.read_text(encoding="utf-8", errors="replace")
            ident = re.search(r"^id:\s*(\S+)", text, re.M)
            title = re.search(r"^title:\s*(.+)$", text, re.M)
            if ident:
                summary = title.group(1).strip().strip("\"'") if title else "architecture decision"
                index[ident.group(1)] = f"{summary} (see {DECISIONS_DIR}/{path.name})"
    return index


# --------------------------------------------------------------------------------------
# Tool implementations
# --------------------------------------------------------------------------------------
class ContextTools:
    """Implements the tools against a project root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    @property
    def map_path(self) -> Path:
        return self.root / MAP_RELATIVE_PATH

    def _read_map(self) -> str:
        try:
            return self.map_path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ToolError(
                f"Project map not found at {self.map_path}. Create it with: python scripts/init_mapping.py "
                "(to install the whole framework: scripts/adopt.py, or /ai-context-mapping:adopt in Claude Code)"
            ) from exc
        except OSError as exc:
            raise ToolError(f"Cannot read the project map: {exc}") from exc

    def read_project_map(self, _arguments: Dict[str, Any]) -> str:
        return self._read_map()

    def normalize(self, raw: str) -> str:
        """Turn user input into a root-relative POSIX path."""
        text = raw.strip().strip("\"'").replace("\\", "/")
        if not text:
            raise InvalidParams("file_path must not be empty")
        if re.match(r"^[A-Za-z]:/", text) or text.startswith("/"):
            try:
                text = Path(text).resolve().relative_to(self.root).as_posix()
            except (ValueError, OSError) as exc:
                raise ToolError(f"'{raw}' is outside the project root {self.root}") from exc
        keep_dir = text.endswith("/")
        text = posixpath.normpath(text)
        if text == "." or text.startswith("../") or text == "..":
            raise ToolError(f"'{raw}' is outside the project root")
        return text + "/" if keep_dir else text

    @staticmethod
    def _lookup(rows: Dict[str, Row], path: str) -> Tuple[Optional[Row], str]:
        """Find the row for ``path``. Returns ``(row, how)`` where how explains the match."""
        for key in (path, path.rstrip("/"), path.rstrip("/") + "/"):
            if key in rows:
                return rows[key], "exact"
        clean = path.rstrip("/")
        for key, row in rows.items():
            if key.endswith("/**") and (clean + "/").startswith(key[:-2]):
                return row, f"covered by group entry '{key}'"
        return None, ""

    def get_file_purpose(self, arguments: Dict[str, Any]) -> str:
        raw = arguments.get("file_path")
        if not isinstance(raw, str):
            raise InvalidParams("'file_path' is required and must be a string")
        path = self.normalize(raw)
        rows = parse_file_index(self._read_map())
        if not rows:
            raise ToolError("The project map has no rows under '## File Index'.")
        row, how = self._lookup(rows, path)
        if row is None:
            known = list(rows)
            suggestions = difflib.get_close_matches(path, known, n=5, cutoff=0.5)
            message = f"'{path}' is not listed in {MAP_RELATIVE_PATH}."
            if suggestions:
                message += " Did you mean: " + ", ".join(suggestions) + "?"
            message += " If the file is new, add it with: python scripts/init_mapping.py --merge"
            raise ToolError(message)

        lines = [f"Path: {path}", f"Category: {row.category}", f"Purpose: {row.purpose}"]
        if how != "exact":
            lines.append(f"Note: {how}")
        ids = _ID_PATTERN.findall(row.invariants)
        if ids:
            index = load_invariant_index(self.root)
            lines.append("Invariants:")
            for ident in dict.fromkeys(ids):
                lines.append(f"  - {ident}: {index.get(ident, 'no definition found in ' + INVARIANTS_DOC + ' or ' + DECISIONS_DIR + '/')}")
            if re.sub(r"[\s,;/()\-]", "", _ID_PATTERN.sub("", row.invariants)):
                lines.append(f"  Notes: {row.invariants}")
        elif row.invariants.strip() not in {"-", ""}:
            lines.append(f"Invariants: {row.invariants}")
        else:
            lines.append("Invariants: none recorded")
        parent = posixpath.dirname(path.rstrip("/"))
        if parent:
            parent_row = rows.get(parent + "/")
            if parent_row:
                lines.append(f"Directory: {parent}/ ({parent_row.category}) - {parent_row.purpose}")
        return "\n".join(lines)

    def get_invariants_for_file(self, arguments: Dict[str, Any]) -> str:
        raw = arguments.get("file_path")
        if not isinstance(raw, str):
            raise InvalidParams("'file_path' is required and must be a string")
        path = self.normalize(raw)
        doc = self.root / INVARIANTS_DOC
        text = doc.read_text(encoding="utf-8", errors="replace") if doc.is_file() else ""
        rules = {rule["id"]: rule for rule in _rule_blocks(text)}
        narratives = _narratives(text)
        try:
            listed_row, _how = self._lookup(parse_file_index(self._read_map()), path)
        except ToolError:
            listed_row = None  # the rules still apply without a map
        listed = _ID_PATTERN.findall(listed_row.invariants) if listed_row else []
        covering = [rule_id for rule_id, rule in rules.items() if rule_covers(rule, path)]
        index = load_invariant_index(self.root)

        lines = [f"Invariants for {path}"]
        for ident in dict.fromkeys(listed + covering):
            sources = []
            if ident in covering:
                sources.append("its scope covers this path")
            if ident in listed:
                sources.append(f"listed in {MAP_RELATIVE_PATH}")
            title = narratives[ident][0] if ident in narratives else index.get(ident, "no definition found")
            lines.append(f"- {ident}: {title} ({'; '.join(sources)})")
            if ident in rules:
                rule = rules[ident]
                lines.append(f"    Rule ({rule.get('type')}): {rule.get('description', '')}".rstrip())
                lines.append(f"    Here: {rule_detail(rule, path)}")
            for note in narratives.get(ident, ("", []))[1]:
                lines.append(f"    {note.strip()}")
        if len(lines) == 1:
            lines.append(f"No invariant covers this path: no rule in {INVARIANTS_DOC} matches it, "
                         "and its map row lists none.")
        decisions = {k: v for k, v in index.items() if k not in rules and k not in narratives}
        if decisions:
            lines.append("Project-wide decisions (they apply to every file):")
            lines.extend(f"- {ident}: {summary}" for ident, summary in decisions.items())
        lines.append("Check the code with: python scripts/verify_invariants.py " + path)
        return "\n".join(lines)

    def check_map(self, _arguments: Dict[str, Any]) -> str:
        rows = parse_file_index(self._read_map())
        if not rows:
            raise ToolError("The project map has no rows under '## File Index'.")
        paths = scan_paths(self.root)
        if MAP_RELATIVE_PATH not in paths:  # the map documents itself even before its first commit
            paths.append(MAP_RELATIVE_PATH)
        missing, stale = map_diff(paths, rows)
        placeholders = [key for key, row in rows.items() if PLACEHOLDER.search(row.purpose)]
        if not (missing or stale or placeholders):
            return f"The map is current: {len(rows)} rows cover all {len(paths)} paths, and every row is described."
        lines = [f"The map needs work ({len(rows)} rows, {len(paths)} paths):"]
        for title, items in (("No row (add it)", missing), ("Stale row (the path is gone)", stale),
                             ("Placeholder description (describe it)", placeholders)):
            if items:
                lines.append(f"{title}:")
                lines.extend(f"  - {item}" for item in items)
        if missing or stale:
            lines.append("Fix: python scripts/init_mapping.py --merge, then write one accurate sentence per new row.")
        if placeholders:
            lines.append("Describe each placeholder row in one accurate sentence; read the file first.")
        return "\n".join(lines)

    def call(self, name: str, arguments: Dict[str, Any]) -> str:
        handlers = {
            "read_project_map": self.read_project_map,
            "get_file_purpose": self.get_file_purpose,
            "get_invariants_for_file": self.get_invariants_for_file,
            "check_map": self.check_map,
        }
        handler = handlers.get(name)
        if handler is None:
            raise InvalidParams(f"unknown tool: {name}")
        return handler(arguments)


# --------------------------------------------------------------------------------------
# JSON-RPC handling
# --------------------------------------------------------------------------------------
def _error(request_id: Any, code: int, message: str) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "error": {"code": code, "message": message}}


def _result(request_id: Any, result: Any) -> Dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def handle_message(message: Any, tools: ContextTools) -> Optional[Dict[str, Any]]:
    """Process one decoded JSON-RPC message; return a response, or None for notifications."""
    if not isinstance(message, dict) or message.get("jsonrpc") != "2.0":
        return _error(message.get("id") if isinstance(message, dict) else None, INVALID_REQUEST, "Invalid JSON-RPC 2.0 request")
    if "method" not in message:
        return None  # a response from the client; this server never sends requests
    method = message["method"]
    is_notification = "id" not in message
    request_id = message.get("id")
    params = message.get("params") or {}
    if not isinstance(method, str) or not isinstance(params, dict):
        return None if is_notification else _error(request_id, INVALID_REQUEST, "method must be a string and params an object")

    if method == "initialize":
        requested = params.get("protocolVersion")
        version = requested if requested in SUPPORTED_PROTOCOLS else SUPPORTED_PROTOCOLS[0]
        return _result(
            request_id,
            {
                "protocolVersion": version,
                "capabilities": {"tools": {"listChanged": False}},
                "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                "instructions": (
                    "Call read_project_map before exploratory searches; call get_file_purpose and "
                    "get_invariants_for_file before editing a file; call check_map after adding or moving files."
                ),
            },
        )
    if method.startswith("notifications/"):
        return None
    if method == "ping":
        return _result(request_id, {})
    if method == "tools/list":
        return _result(request_id, {"tools": TOOLS})
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if not isinstance(name, str) or not isinstance(arguments, dict):
            return _error(request_id, INVALID_PARAMS, "tools/call requires a string 'name' and an object 'arguments'")
        try:
            text = tools.call(name, arguments)
            return _result(request_id, {"content": [{"type": "text", "text": text}], "isError": False})
        except InvalidParams as exc:
            return _error(request_id, INVALID_PARAMS, str(exc))
        except ToolError as exc:
            return _result(request_id, {"content": [{"type": "text", "text": str(exc)}], "isError": True})
    if is_notification:
        return None
    return _error(request_id, METHOD_NOT_FOUND, f"Method not found: {method}")


def dispatch(raw: str, tools: ContextTools) -> Optional[str]:
    """Decode one line of input and return the encoded response line, if any."""
    try:
        decoded = json.loads(raw)
    except ValueError:
        return json.dumps(_error(None, PARSE_ERROR, "Parse error"))
    try:
        if isinstance(decoded, list):
            responses = [r for r in (handle_message(item, tools) for item in decoded) if r is not None]
            return json.dumps(responses) if responses else None
        response = handle_message(decoded, tools)
    except Exception as exc:  # noqa: BLE001 - the server must survive any handler bug
        log(f"internal error: {exc!r}")
        request_id = decoded.get("id") if isinstance(decoded, dict) else None
        return json.dumps(_error(request_id, INTERNAL_ERROR, f"Internal error: {exc}"))
    return json.dumps(response) if response is not None else None


def serve(tools: ContextTools) -> int:
    """Run the stdio loop until the client closes stdin."""
    for stream, kwargs in ((sys.stdin, {"encoding": "utf-8"}), (sys.stdout, {"encoding": "utf-8", "newline": "\n"})):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(**kwargs)
    log(f"serving {tools.root}")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        log(f"<- {line[:200]}")
        reply = dispatch(line, tools)
        if reply is not None:
            sys.stdout.write(reply + "\n")
            sys.stdout.flush()
            log(f"-> {reply[:200]}")
    return 0


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="context_server.py",
        description="MCP stdio server exposing read_project_map, get_file_purpose, get_invariants_for_file, and check_map.",
        epilog=(
            "Register it in your MCP client (see mcp/README.md). Diagnostics go to stderr when\n"
            "AI_CONTEXT_DEBUG=1 is set; stdout carries protocol messages only."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", help="project root (default: $AI_CONTEXT_ROOT, else the parent of this file's directory)")
    parser.add_argument("--check", action="store_true", help="validate the project map and exit")
    parser.add_argument("--call", metavar="TOOL", help="run one tool from the command line and print its output")
    parser.add_argument("--arg", action="append", default=[], metavar="KEY=VALUE", help="argument for --call; repeatable")
    parser.add_argument("--version", action="version", version=f"%(prog)s {SERVER_VERSION}")
    return parser


def resolve_root(explicit: Optional[str]) -> Path:
    chosen = explicit or os.environ.get("AI_CONTEXT_ROOT")
    return Path(chosen).expanduser().resolve() if chosen else Path(__file__).resolve().parent.parent


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    root = resolve_root(args.root)
    tools = ContextTools(root)

    if args.check:
        try:
            rows = parse_file_index(tools._read_map())
        except ToolError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        if not rows:
            print("error: the map has no rows under '## File Index'", file=sys.stderr)
            return 1
        print(f"ok: {len(rows)} entries in {tools.map_path}")
        return 0

    if args.call:
        arguments: Dict[str, Any] = {}
        for item in args.arg:
            if "=" not in item:
                print(f"error: --arg expects KEY=VALUE, got {item!r}", file=sys.stderr)
                return 2
            key, _, value = item.partition("=")
            arguments[key] = value
        try:
            print(tools.call(args.call, arguments))
            return 0
        except (ToolError, InvalidParams) as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1

    return serve(tools)


if __name__ == "__main__":
    sys.exit(main())
