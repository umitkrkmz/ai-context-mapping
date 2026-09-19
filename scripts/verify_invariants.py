#!/usr/bin/env python3
"""Statically verify architectural invariants using Python's ``ast`` module.

Rules come from two machine-readable sources:

1. ``invariants/negative-invariants.md`` -- fenced blocks whose info string is
   ``invariant-rule`` and whose body is a JSON object (or a list of objects).
2. ``decisions/*.yaml`` -- an architecture decision may list ``forbidden_imports``;
   each entry becomes a project-wide import ban. The decision files are also linted
   for the required fields ``id``, ``decision``, ``reason``, and ``forbidden_actions``.

Supported rule types:

    forbidden-import  Files in ``scope`` must not import the listed modules.
                      Fields: forbidden, scope, exclude, allow_in
    isolated-import   The listed modules may only be imported inside the wrapper files.
                      Fields: modules, allowed_in, use, scope, exclude
    stdlib-only       Files in ``scope`` may only import the standard library or local
                      modules. Fields: allow, scope, exclude
    forbidden-call    Calls to the listed qualified names (``os.system``, ``eval``) are
                      banned, even through import aliases. Fields: calls, scope, exclude,
                      allow_in
    required-text     A file must still contain the given strings (guards that must
                      never be deleted). Fields: file, contains

Import bypasses are detected too: relative imports are resolved, and constant-string
``__import__()`` / ``importlib.import_module()`` calls count as imports.

Exit codes: 0 = no violations, 1 = violations found, 2 = configuration error.

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
INVARIANTS_DOC = "invariants/negative-invariants.md"
DECISIONS_DIR = "decisions"
FENCE_LINE = re.compile(r"^ {0,3}(`{3,}|~{3,})\s*([^\s`]*)\s*$")
RULE_INFO = "invariant-rule"
RULE_TYPES = {"forbidden-import", "isolated-import", "stdlib-only", "forbidden-call", "required-text"}
REQUIRED_RULE_FIELDS = {
    "forbidden-import": ("forbidden",),
    "isolated-import": ("modules", "allowed_in"),
    "stdlib-only": (),
    "forbidden-call": ("calls",),
    "required-text": ("file", "contains"),
}
REQUIRED_DECISION_FIELDS = ("id", "decision", "reason", "forbidden_actions")
SKIP_DIRS = {
    ".git", ".hg", ".svn", "__pycache__", "node_modules", ".venv", "venv", "env", ".tox",
    ".nox", ".mypy_cache", ".pytest_cache", ".ruff_cache", "build", "dist", ".eggs",
}
DYNAMIC_IMPORTERS = {"__import__", "importlib.import_module", "importlib.__import__"}

# Fallback for Python < 3.10, where ``sys.stdlib_module_names`` does not exist.
_STDLIB_FALLBACK = frozenset(
    """__future__ _thread abc aifc argparse array ast asynchat asyncio asyncore atexit audioop
    base64 bdb binascii binhex bisect builtins bz2 cProfile calendar cgi cgitb chunk cmath cmd
    code codecs codeop collections colorsys compileall concurrent configparser contextlib
    contextvars copy copyreg crypt csv ctypes curses dataclasses datetime dbm decimal difflib
    dis distutils doctest email encodings ensurepip enum errno faulthandler fcntl filecmp
    fileinput fnmatch fractions ftplib functools gc genericpath getopt getpass gettext glob
    graphlib grp gzip hashlib heapq hmac html http idlelib imaplib imghdr imp importlib inspect
    io ipaddress itertools json keyword lib2to3 linecache locale logging lzma mailbox mailcap
    marshal math mimetypes mmap modulefinder msilib msvcrt multiprocessing netrc nis nntplib nt
    ntpath numbers opcode operator optparse os ossaudiodev pathlib pdb pickle pickletools pipes
    pkgutil platform plistlib poplib posix posixpath pprint profile pstats pty pwd py_compile
    pyclbr pydoc pydoc_data queue quopri random re readline reprlib resource rlcompleter runpy
    sched secrets select selectors shelve shlex shutil signal site smtpd smtplib sndhdr socket
    socketserver spwd sqlite3 sre_compile sre_constants sre_parse ssl stat statistics string
    stringprep struct subprocess sunau symtable sys sysconfig syslog tabnanny tarfile telnetlib
    tempfile termios textwrap this threading time timeit tkinter token tokenize tomllib trace
    traceback tracemalloc tty turtle turtledemo types typing unicodedata unittest urllib uu uuid
    venv warnings wave weakref webbrowser winreg winsound wsgiref xdrlib xml xmlrpc zipapp
    zipfile zipimport zlib zoneinfo""".split()
)
STDLIB_MODULES = frozenset(getattr(sys, "stdlib_module_names", ())) | _STDLIB_FALLBACK


# --------------------------------------------------------------------------------------
# Terminal formatting
# --------------------------------------------------------------------------------------
def supports_color(stream) -> bool:
    """Return True when ANSI colors are safe to print on ``stream``."""
    if os.environ.get("NO_COLOR"):
        return False
    if os.environ.get("FORCE_COLOR"):
        return True
    if not hasattr(stream, "isatty") or not stream.isatty():
        return False
    if os.name == "nt":
        return bool(os.environ.get("WT_SESSION") or os.environ.get("ANSICON") or os.environ.get("TERM"))
    return os.environ.get("TERM") != "dumb"


class Style:
    """Tiny ANSI helper that degrades to plain text."""

    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

    def _wrap(self, code: str, text: str) -> str:
        return f"\033[{code}m{text}\033[0m" if self.enabled else text

    def bold(self, text: str) -> str:
        return self._wrap("1", text)

    def dim(self, text: str) -> str:
        return self._wrap("2", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def cyan(self, text: str) -> str:
        return self._wrap("36", text)


# --------------------------------------------------------------------------------------
# Data model
# --------------------------------------------------------------------------------------
class ConfigError(Exception):
    """Raised when a rule or decision file is malformed."""


@dataclass
class Rule:
    id: str
    type: str
    description: str
    params: Dict[str, Any]
    source: str
    scope: List[str] = field(default_factory=lambda: ["**/*.py"])
    exclude: List[str] = field(default_factory=list)


@dataclass(frozen=True)
class Violation:
    rule_id: str
    path: str
    line: int
    message: str

    def as_dict(self) -> Dict[str, Any]:
        return {"rule": self.rule_id, "path": self.path, "line": self.line, "message": self.message}


@dataclass(frozen=True)
class ImportRef:
    """One import statement. ``candidates`` are the dotted names a rule may match against."""

    base: str
    candidates: Tuple[str, ...]
    line: int
    relative: bool = False
    dynamic: bool = False


@dataclass(frozen=True)
class CallRef:
    qualified: str
    line: int


# --------------------------------------------------------------------------------------
# Glob matching
# --------------------------------------------------------------------------------------
_GLOB_CACHE: Dict[str, "re.Pattern[str]"] = {}


def glob_to_regex(pattern: str) -> "re.Pattern[str]":
    """Compile a glob supporting ``**`` (any depth), ``*`` and ``?`` within one segment."""
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


def matches_any(path: str, patterns: Iterable[str]) -> bool:
    return any(glob_to_regex(p).match(path) for p in patterns)


# --------------------------------------------------------------------------------------
# Minimal YAML reader (flat maps of scalars, block scalars, and lists of scalars)
# --------------------------------------------------------------------------------------
class YamlError(ValueError):
    """Raised for YAML constructs outside the supported subset."""


def _split_inline_list(body: str) -> List[str]:
    items: List[str] = []
    current: List[str] = []
    quote = ""
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = ""
        elif char in "\"'":
            quote = char
            current.append(char)
        elif char == ",":
            items.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def _parse_scalar(token: str) -> Any:
    text = token.strip()
    if text.startswith('"') and text.endswith('"') and len(text) >= 2:
        try:
            return json.loads(text)
        except ValueError as exc:
            raise YamlError(f"invalid double-quoted string: {text}") from exc
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        return text[1:-1].replace("''", "'")
    if text.startswith("[") and text.endswith("]"):
        return [_parse_scalar(part) for part in _split_inline_list(text[1:-1])]
    text = re.sub(r"\s+#.*$", "", text)
    lowered = text.lower()
    if lowered in {"null", "~", ""}:
        return None
    if lowered in {"true", "yes"}:
        return True
    if lowered in {"false", "no"}:
        return False
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    return text


def parse_simple_yaml(text: str) -> Dict[str, Any]:
    """Parse the YAML subset used by decision records.

    Supported: ``key: scalar``, ``key: [a, b]``, ``key: |`` / ``key: >`` block scalars, and
    ``key:`` followed by ``- item`` lines. Nested mappings raise :class:`YamlError`.
    """
    lines = text.splitlines()
    data: Dict[str, Any] = {}
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = raw.strip()
        if not stripped or stripped.startswith("#") or stripped in {"---", "..."}:
            i += 1
            continue
        if raw[0] in " \t":
            raise YamlError(f"line {i + 1}: unexpected indentation (nested mappings are not supported)")
        match = re.match(r"^([A-Za-z_][\w-]*):(?:\s+(.*))?$", raw.rstrip())
        if not match:
            raise YamlError(f"line {i + 1}: expected 'key: value', got {raw.strip()!r}")
        key, rest = match.group(1), (match.group(2) or "").strip()
        i += 1
        if rest in {"|", "|-", ">", ">-"}:
            block: List[str] = []
            while i < len(lines) and (not lines[i].strip() or lines[i][0] in " \t"):
                block.append(lines[i])
                i += 1
            indents = [len(b) - len(b.lstrip()) for b in block if b.strip()]
            indent = min(indents) if indents else 0
            content = [b[indent:] if b.strip() else "" for b in block]
            while content and content[-1] == "":
                content.pop()
            if rest.startswith("|"):
                data[key] = "\n".join(content)
            else:
                paragraphs = "\n".join(content).split("\n\n")
                data[key] = "\n".join(" ".join(p.split()) for p in paragraphs)
        elif rest == "":
            items: List[Any] = []
            while i < len(lines):
                line = lines[i]
                body = line.strip()
                if not body or body.startswith("#"):
                    i += 1
                    continue
                if body == "-" or body.startswith("- "):
                    item = body[1:].strip()
                    if re.match(r"^[A-Za-z_][\w-]*:\s+\S", item) and item[0] not in "\"'":
                        raise YamlError(
                            f"line {i + 1}: list items must be scalars; quote strings that contain ': '"
                        )
                    items.append(_parse_scalar(item))
                    i += 1
                else:
                    break
            data[key] = items if items else None
        else:
            data[key] = _parse_scalar(rest)
    return data


# --------------------------------------------------------------------------------------
# Rule loading
# --------------------------------------------------------------------------------------
def _as_str_list(value: Any, where: str, name: str) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return list(value)
    raise ConfigError(f"{where}: field '{name}' must be a string or a list of strings")


def rule_from_dict(raw: Any, source: str) -> Rule:
    """Validate one decoded rule object and convert it into a :class:`Rule`."""
    if not isinstance(raw, dict):
        raise ConfigError(f"{source}: each rule must be a JSON object")
    rule_id = raw.get("id")
    rule_type = raw.get("type")
    if not isinstance(rule_id, str) or not rule_id:
        raise ConfigError(f"{source}: rule is missing a string 'id'")
    if rule_type not in RULE_TYPES:
        raise ConfigError(f"{source}: rule {rule_id} has unknown type {rule_type!r}; expected one of {sorted(RULE_TYPES)}")
    for name in REQUIRED_RULE_FIELDS[rule_type]:
        if name not in raw:
            raise ConfigError(f"{source}: rule {rule_id} ({rule_type}) requires field '{name}'")
    params: Dict[str, Any] = {}
    for name in ("forbidden", "modules", "allowed_in", "allow", "calls", "contains", "allow_in"):
        if name in raw:
            params[name] = _as_str_list(raw[name], f"{source} rule {rule_id}", name)
    for name in ("file", "use"):
        if name in raw:
            if not isinstance(raw[name], str):
                raise ConfigError(f"{source}: rule {rule_id} field '{name}' must be a string")
            params[name] = raw[name]
    rule = Rule(
        id=rule_id,
        type=rule_type,
        description=str(raw.get("description", "")).strip(),
        params=params,
        source=source,
    )
    if "scope" in raw:
        rule.scope = _as_str_list(raw["scope"], f"{source} rule {rule_id}", "scope")
    if "exclude" in raw:
        rule.exclude = _as_str_list(raw["exclude"], f"{source} rule {rule_id}", "exclude")
    return rule


def extract_rule_blocks(text: str) -> List[Tuple[int, str]]:
    """Return ``(line_number, body)`` for each top-level ``invariant-rule`` fenced block.

    Blocks nested inside another fence (for example a template shown in a four-backtick
    Markdown example) are documentation, not live rules, and are skipped.
    """
    blocks: List[Tuple[int, str]] = []
    fence: Optional[Tuple[str, int, str, int]] = None
    body: List[str] = []
    for number, line in enumerate(text.splitlines(), start=1):
        match = FENCE_LINE.match(line)
        if fence is None:
            if match:
                fence = (match.group(1)[0], len(match.group(1)), match.group(2), number)
                body = []
            continue
        char, length, info, opened_at = fence
        if match and match.group(1)[0] == char and len(match.group(1)) >= length and not match.group(2):
            if info == RULE_INFO:
                blocks.append((opened_at, "\n".join(body)))
            fence = None
        else:
            body.append(line)
    return blocks


def load_rules_from_markdown(path: Path, display: str) -> List[Rule]:
    """Extract every ``invariant-rule`` fenced block from a Markdown file."""
    rules: List[Rule] = []
    for line_no, body in extract_rule_blocks(path.read_text(encoding="utf-8")):
        try:
            decoded = json.loads(body)
        except ValueError as exc:
            raise ConfigError(f"{display}:{line_no}: invalid JSON in invariant-rule block ({exc})") from exc
        for item in decoded if isinstance(decoded, list) else [decoded]:
            rules.append(rule_from_dict(item, f"{display}:{line_no}"))
    return rules


def load_rules_from_json(path: Path, display: str) -> List[Rule]:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except ValueError as exc:
        raise ConfigError(f"{display}: invalid JSON ({exc})") from exc
    return [rule_from_dict(item, display) for item in (decoded if isinstance(decoded, list) else [decoded])]


def load_decisions(root: Path) -> Tuple[List[Rule], List[Violation]]:
    """Lint decision records and derive import-ban rules from ``forbidden_imports``."""
    rules: List[Rule] = []
    problems: List[Violation] = []
    directory = root / DECISIONS_DIR
    if not directory.is_dir():
        return rules, problems
    for path in sorted(list(directory.glob("*.yaml")) + list(directory.glob("*.yml"))):
        display = path.relative_to(root).as_posix()
        try:
            record = parse_simple_yaml(path.read_text(encoding="utf-8"))
        except YamlError as exc:
            problems.append(Violation("ADR-FORMAT", display, 1, f"cannot parse decision record: {exc}"))
            continue
        for name in REQUIRED_DECISION_FIELDS:
            if record.get(name) in (None, "", []):
                problems.append(Violation("ADR-FORMAT", display, 1, f"missing required field '{name}'"))
        if record.get("forbidden_actions") not in (None, "", []) and not isinstance(record.get("forbidden_actions"), list):
            problems.append(Violation("ADR-FORMAT", display, 1, "'forbidden_actions' must be a list"))
        prefix = re.match(r"^(\d+)-", path.name)
        digits = re.search(r"(\d+)\s*$", str(record.get("id", "")))
        if prefix and digits and int(prefix.group(1)) != int(digits.group(1)):
            problems.append(
                Violation("ADR-FORMAT", display, 1, f"id {record.get('id')!r} does not match the file name prefix {prefix.group(1)}")
            )
        banned = record.get("forbidden_imports")
        if isinstance(banned, list) and banned:
            rules.append(
                Rule(
                    id=str(record.get("id", path.stem)),
                    type="forbidden-import",
                    description=str(record.get("title") or record.get("decision") or "").strip().splitlines()[0]
                    if (record.get("title") or record.get("decision"))
                    else "",
                    params={"forbidden": [str(b) for b in banned]},
                    source=display,
                    scope=["**/*.py"],
                    exclude=["templates/**", "docs/**"],
                )
            )
    return rules, problems


# --------------------------------------------------------------------------------------
# AST analysis
# --------------------------------------------------------------------------------------
def module_name_for(rel_path: str) -> Tuple[str, bool]:
    """Return ``(dotted_module_name, is_package_init)`` for a repository-relative path."""
    parts = rel_path[:-3].split("/") if rel_path.endswith(".py") else rel_path.split("/")
    is_package = parts[-1] == "__init__"
    if is_package:
        parts = parts[:-1]
    return ".".join(parts), is_package


def resolve_relative(module_name: str, is_package: bool, level: int, target: Optional[str]) -> str:
    """Resolve a relative import (``from ..x import y``) into an absolute dotted name."""
    parts = module_name.split(".") if module_name else []
    if not is_package and parts:
        parts = parts[:-1]
    if level > 1:
        parts = parts[: max(0, len(parts) - (level - 1))]
    if target:
        parts = parts + target.split(".")
    return ".".join(parts)


def dotted_name(node: ast.AST) -> Optional[List[str]]:
    """Return ``['a', 'b', 'c']`` for an ``a.b.c`` expression, or None if it is not a plain chain."""
    parts: List[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
        return list(reversed(parts))
    return None


class FileFacts:
    """Imports and calls extracted from one Python source file."""

    def __init__(self, rel_path: str, source: str) -> None:
        self.path = rel_path
        self.imports: List[ImportRef] = []
        self.calls: List[CallRef] = []
        tree = ast.parse(source, filename=rel_path)
        module_name, is_package = module_name_for(rel_path)
        aliases = self._collect_aliases(tree, module_name, is_package)
        self._collect(tree, aliases, module_name, is_package)

    @staticmethod
    def _collect_aliases(tree: ast.AST, module_name: str, is_package: bool) -> Dict[str, str]:
        aliases: Dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.asname:
                        aliases[alias.asname] = alias.name
                    else:
                        top = alias.name.split(".")[0]
                        aliases[top] = top
            elif isinstance(node, ast.ImportFrom):
                base = (
                    resolve_relative(module_name, is_package, node.level, node.module)
                    if node.level
                    else (node.module or "")
                )
                for alias in node.names:
                    if alias.name != "*":
                        aliases[alias.asname or alias.name] = f"{base}.{alias.name}" if base else alias.name
        return aliases

    def _collect(self, tree: ast.AST, aliases: Dict[str, str], module_name: str, is_package: bool) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.imports.append(ImportRef(alias.name, (alias.name,), node.lineno))
            elif isinstance(node, ast.ImportFrom):
                if node.level:
                    base = resolve_relative(module_name, is_package, node.level, node.module)
                    relative = True
                else:
                    base = node.module or ""
                    relative = False
                names = [a.name for a in node.names if a.name != "*"]
                candidates = tuple([base] + [f"{base}.{n}" if base else n for n in names])
                self.imports.append(ImportRef(base, candidates, node.lineno, relative=relative))
            elif isinstance(node, ast.Call):
                chain = dotted_name(node.func)
                if not chain:
                    continue
                head = aliases.get(chain[0], chain[0])
                qualified = ".".join([head] + chain[1:])
                self.calls.append(CallRef(qualified, node.lineno))
                if qualified in DYNAMIC_IMPORTERS and node.args:
                    first = node.args[0]
                    if isinstance(first, ast.Constant) and isinstance(first.value, str):
                        self.imports.append(ImportRef(first.value, (first.value,), node.lineno, dynamic=True))


def matches_prefix(name: str, prefixes: Iterable[str]) -> Optional[str]:
    """Return the first prefix that equals ``name`` or is a dotted ancestor of it."""
    for prefix in prefixes:
        if name == prefix or name.startswith(prefix + "."):
            return prefix
    return None


# --------------------------------------------------------------------------------------
# Rule evaluation
# --------------------------------------------------------------------------------------
def _is_local_module(root: Path, rel_path: str, top_level: str) -> bool:
    file_dir = (root / rel_path).parent
    return (
        (root / top_level).is_dir()
        or (root / f"{top_level}.py").is_file()
        or (file_dir / top_level).is_dir()
        or (file_dir / f"{top_level}.py").is_file()
    )


def check_forbidden_import(rule: Rule, facts: FileFacts) -> List[Violation]:
    if matches_any(facts.path, rule.params.get("allow_in", [])):
        return []
    found: List[Violation] = []
    for ref in facts.imports:
        for candidate in ref.candidates:
            hit = matches_prefix(candidate, rule.params["forbidden"])
            if hit:
                how = "dynamically imports" if ref.dynamic else "imports"
                found.append(Violation(rule.id, facts.path, ref.line, f"{how} forbidden module '{candidate}' (banned: '{hit}')"))
                break
    return found


def check_isolated_import(rule: Rule, facts: FileFacts) -> List[Violation]:
    if matches_any(facts.path, rule.params["allowed_in"]):
        return []
    wrapper = rule.params.get("use") or ", ".join(rule.params["allowed_in"])
    found: List[Violation] = []
    for ref in facts.imports:
        for candidate in ref.candidates:
            hit = matches_prefix(candidate, rule.params["modules"])
            if hit:
                found.append(
                    Violation(rule.id, facts.path, ref.line, f"imports isolated module '{candidate}'; go through the wrapper: {wrapper}")
                )
                break
    return found


def check_stdlib_only(rule: Rule, facts: FileFacts, root: Path) -> List[Violation]:
    allowed = set(rule.params.get("allow", []))
    found: List[Violation] = []
    for ref in facts.imports:
        if ref.relative or not ref.base:
            continue
        top = ref.base.split(".")[0]
        if top in STDLIB_MODULES or top in allowed or _is_local_module(root, facts.path, top):
            continue
        how = "dynamically imports" if ref.dynamic else "imports"
        found.append(Violation(rule.id, facts.path, ref.line, f"{how} third-party module '{top}'; only the standard library is allowed"))
    return found


def check_forbidden_call(rule: Rule, facts: FileFacts) -> List[Violation]:
    if matches_any(facts.path, rule.params.get("allow_in", [])):
        return []
    found: List[Violation] = []
    for call in facts.calls:
        for pattern in rule.params["calls"]:
            if fnmatch.fnmatchcase(call.qualified, pattern):
                found.append(Violation(rule.id, facts.path, call.line, f"calls forbidden function '{call.qualified}()'"))
                break
    return found


def check_required_text(rule: Rule, root: Path) -> List[Violation]:
    target = rule.params["file"]
    path = root / target
    if not path.is_file():
        return [Violation(rule.id, target, 1, "required file is missing")]
    text = path.read_text(encoding="utf-8", errors="replace")
    return [
        Violation(rule.id, target, 1, f"required text was removed: {needle!r}")
        for needle in rule.params["contains"]
        if needle not in text
    ]


# --------------------------------------------------------------------------------------
# Driver
# --------------------------------------------------------------------------------------
def iter_python_files(root: Path, only: Sequence[str]) -> List[str]:
    """Return repository-relative POSIX paths of Python files to analyze."""
    if only:
        result: List[str] = []
        for item in only:
            candidate = (root / item) if not os.path.isabs(item) else Path(item)
            if candidate.is_dir():
                result.extend(_walk(root, candidate))
            elif candidate.suffix == ".py" and candidate.is_file():
                result.append(candidate.resolve().relative_to(root).as_posix())
        return sorted(set(result))
    return _walk(root, root)


def _walk(root: Path, start: Path) -> List[str]:
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(start):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        for name in sorted(filenames):
            if name.endswith(".py"):
                found.append((Path(dirpath) / name).resolve().relative_to(root).as_posix())
    return found


def verify(root: Path, rules: Sequence[Rule], only: Sequence[str]) -> Tuple[List[Violation], List[str], int]:
    """Run every rule. Returns ``(violations, warnings, files_scanned)``."""
    violations: List[Violation] = []
    warnings: List[str] = []
    files = iter_python_files(root, only)
    facts_cache: Dict[str, Optional[FileFacts]] = {}

    def facts_for(rel_path: str) -> Optional[FileFacts]:
        if rel_path not in facts_cache:
            try:
                source = (root / rel_path).read_text(encoding="utf-8")
                facts_cache[rel_path] = FileFacts(rel_path, source)
            except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
                warnings.append(f"{rel_path}: skipped, cannot parse ({exc})")
                facts_cache[rel_path] = None
        return facts_cache[rel_path]

    for rule in rules:
        if rule.type == "required-text":
            violations.extend(check_required_text(rule, root))
            continue
        for rel_path in files:
            if not matches_any(rel_path, rule.scope) or matches_any(rel_path, rule.exclude):
                continue
            facts = facts_for(rel_path)
            if facts is None:
                continue
            if rule.type == "forbidden-import":
                violations.extend(check_forbidden_import(rule, facts))
            elif rule.type == "isolated-import":
                violations.extend(check_isolated_import(rule, facts))
            elif rule.type == "stdlib-only":
                violations.extend(check_stdlib_only(rule, facts, root))
            elif rule.type == "forbidden-call":
                violations.extend(check_forbidden_call(rule, facts))
    violations.sort(key=lambda v: (v.path, v.line, v.rule_id))
    return violations, warnings, len(files)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="verify_invariants.py",
        description="AST-based checker for forbidden imports, isolated wrappers, and protected guards.",
        epilog=(
            "rule blocks look like this inside invariants/negative-invariants.md:\n\n"
            "  ```invariant-rule\n"
            '  {"id": "NI-001", "type": "stdlib-only", "scope": ["scripts/**/*.py"]}\n'
            "  ```\n\n"
            "exit codes: 0 ok, 1 violations found, 2 configuration error"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("paths", nargs="*", help="files or directories to check (default: whole repository)")
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--rules", action="append", default=[], metavar="FILE", help="extra rule file (.md with rule blocks, or .json); repeatable")
    parser.add_argument("--no-decisions", action="store_true", help="do not lint decisions/*.yaml or derive rules from them")
    parser.add_argument("--list-rules", action="store_true", help="print the loaded rules and exit")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="output format (default: text)")
    parser.add_argument("--strict", action="store_true", help="treat unparsable files as failures")
    parser.add_argument("--require-rules", action="store_true", help="fail with exit code 2 when no rules are found")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def load_all_rules(root: Path, extra: Sequence[str], include_decisions: bool) -> Tuple[List[Rule], List[Violation]]:
    rules: List[Rule] = []
    problems: List[Violation] = []
    default_doc = root / INVARIANTS_DOC
    if default_doc.is_file():
        rules.extend(load_rules_from_markdown(default_doc, INVARIANTS_DOC))
    for item in extra:
        path = Path(item) if os.path.isabs(item) else root / item
        if not path.is_file():
            raise ConfigError(f"rules file not found: {item}")
        loader = load_rules_from_json if path.suffix.lower() == ".json" else load_rules_from_markdown
        rules.extend(loader(path, item))
    if include_decisions:
        derived, decision_problems = load_decisions(root)
        rules.extend(derived)
        problems.extend(decision_problems)
    seen: Dict[str, str] = {}
    for rule in rules:
        if rule.id in seen and rule.type != "forbidden-import":
            raise ConfigError(f"duplicate rule id {rule.id} in {rule.source} and {seen[rule.id]}")
        seen[rule.id] = rule.source
    return rules, problems


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    style = Style(supports_color(sys.stdout) and not args.no_color)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(style.red(f"error: root is not a directory: {root}"), file=sys.stderr)
        return 2
    try:
        rules, problems = load_all_rules(root, args.rules, not args.no_decisions)
    except (ConfigError, OSError) as exc:
        print(style.red(f"configuration error: {exc}"), file=sys.stderr)
        return 2
    if args.require_rules and not rules:
        print(style.red("configuration error: no invariant rules were found"), file=sys.stderr)
        return 2

    if args.list_rules:
        for rule in rules:
            print(f"{style.bold(rule.id):<10} {rule.type:<16} {rule.description or '(no description)'}")
            print(style.dim(f"           source: {rule.source}"))
        return 0

    try:
        violations, warnings, scanned = verify(root, rules, args.paths)
    except (OSError, ValueError) as exc:
        print(style.red(f"error: {exc}"), file=sys.stderr)
        return 2
    violations = sorted(problems + violations, key=lambda v: (v.path, v.line, v.rule_id))
    failed = bool(violations) or (args.strict and bool(warnings))

    if args.format == "json":
        print(
            json.dumps(
                {
                    "ok": not failed,
                    "files_scanned": scanned,
                    "rules": [r.id for r in rules],
                    "violations": [v.as_dict() for v in violations],
                    "warnings": warnings,
                },
                indent=2,
            )
        )
        return 1 if failed else 0

    print(style.bold("Invariant check") + style.dim(f"  ({scanned} Python files, {len(rules)} rules)"))
    if not rules:
        print(style.yellow("[warn] no invariant rules found; add 'invariant-rule' blocks to " + INVARIANTS_DOC))
    descriptions = {r.id: r.description for r in rules}
    for violation in violations:
        print(style.red("[FAIL]") + f" {violation.rule_id:<9} {violation.path}:{violation.line}  {violation.message}")
        if descriptions.get(violation.rule_id):
            print(style.dim(f"         rule: {descriptions[violation.rule_id]}"))
    for warning in warnings:
        print(style.yellow("[warn]") + f" {warning}")
    if violations:
        print(
            f"\n{style.red(str(len(violations)) + ' violation(s)')}. If a change is intentional, get the user's approval "
            f"and update {INVARIANTS_DOC} in the same commit."
        )
    elif failed:
        print(style.red("\nStrict mode: unparsable files count as failures."))
    else:
        print(style.green("[ok] all invariants hold."))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
