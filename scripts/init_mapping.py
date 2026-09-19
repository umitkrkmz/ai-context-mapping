#!/usr/bin/env python3
"""Generate or refresh ``maps/project-map.md`` for the current repository.

The project map is the first thing an AI agent reads. This tool scans the directory tree
(honoring ``.agentignore``), assigns every file and directory a category and a purpose,
detects routes and entry points, and writes a Markdown map that other guardrails consume:

* ``tests/test_maps.py`` fails when a file is missing from the map.
* ``mcp/context_server.py`` serves the map to Claude Desktop and Cursor.

Modes:
    (default)  Create a new map. Refuses to overwrite an existing one.
    --merge    Keep hand-written rows, add rows for new paths, drop rows for deleted paths.
    --force    Regenerate the map from scratch (hand-written rows are lost).
    --check    Read-only. Exit 1 if the map is missing entries or has stale ones.
    --stats    Read-only. Report repository size, map size, and estimated token savings.

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import ast
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Set, Tuple

VERSION = "1.0.0"
MAP_RELATIVE_PATH = "maps/project-map.md"
IGNORE_FILE_NAME = ".agentignore"
FILE_INDEX_TITLE = "File Index"
ROUTE_TABLE_TITLE = "Route Table"
ALWAYS_IGNORED = (".git/", "__pycache__/", ".pytest_cache/")
MAX_READ_BYTES = 512 * 1024
MAX_PURPOSE_CHARS = 110
DEFAULT_COLLAPSE_THRESHOLD = 40
CHARS_PER_TOKEN = 4
INSTRUCTION_LINE_LIMIT = 500
MAP_TOKEN_WARNING = 3000
INSTRUCTION_FILES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", ".cursorrules", ".github/copilot-instructions.md")

CATEGORY_HELP: Dict[str, str] = {
    "manifesto": "Rules and instructions addressed to AI agents.",
    "ignore": "Ignore lists that keep files out of context or version control.",
    "map": "Navigation maps of the repository.",
    "decision": "Machine-readable architecture decision records.",
    "invariant": "Negative invariants: what must not be refactored or removed.",
    "persona": "Role-specific system prompts for AI workflows.",
    "ci": "Continuous integration and automation pipelines.",
    "docs": "Human-oriented documentation.",
    "legal": "License and legal notices.",
    "test": "Automated tests and test fixtures.",
    "script": "Command-line tooling and automation scripts.",
    "integration": "Servers and adapters that connect to external tools.",
    "template": "Boilerplate meant to be copied into other projects.",
    "source": "Application or library source code.",
    "config": "Configuration and settings files.",
    "dependency": "Dependency manifests.",
    "build": "Build, packaging, and container definitions.",
    "data": "Data files and fixtures.",
    "asset": "Images, fonts, and other static assets.",
    "directory": "A directory that groups files without a more specific role.",
    "other": "Files that fit no other category.",
}

CODE_EXTENSIONS = {
    ".py", ".pyi", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".go", ".rs", ".java",
    ".kt", ".kts", ".swift", ".c", ".h", ".cc", ".cpp", ".hpp", ".cs", ".rb", ".php",
    ".scala", ".lua", ".dart", ".vue", ".svelte", ".sql", ".r",
}
CONFIG_EXTENSIONS = {".json", ".toml", ".yaml", ".yml", ".ini", ".cfg", ".conf", ".xml", ".properties"}
DATA_EXTENSIONS = {".csv", ".tsv", ".txt", ".jsonl", ".ndjson", ".parquet"}
ASSET_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico", ".webp", ".woff", ".woff2", ".ttf", ".css", ".scss", ".less"}
SCRIPT_EXTENSIONS = {".sh", ".bash", ".zsh", ".ps1", ".bat", ".cmd"}
DOC_EXTENSIONS = {".md", ".mdx", ".rst", ".adoc"}

KNOWN_FILES: Dict[str, Tuple[str, str]] = {
    "AGENTS.md": ("manifesto", "Operating manifesto for AI agents."),
    "CLAUDE.md": ("manifesto", "Claude Code entry point; mirrors AGENTS.md."),
    "GEMINI.md": ("manifesto", "Gemini CLI entry point for agent instructions."),
    ".cursorrules": ("manifesto", "Legacy Cursor rules file."),
    ".agentignore": ("ignore", "Paths excluded from agent context."),
    ".gitignore": ("ignore", "Paths excluded from version control."),
    ".dockerignore": ("ignore", "Paths excluded from Docker build contexts."),
    ".cursorignore": ("ignore", "Paths excluded from Cursor indexing."),
    ".gitattributes": ("config", "Git attributes such as line-ending rules."),
    "LICENSE": ("legal", "Software license."),
    "LICENSE.md": ("legal", "Software license."),
    "README.md": ("docs", "Project overview and quickstart."),
    "CHANGELOG.md": ("docs", "History of notable changes."),
    "CONTRIBUTING.md": ("docs", "Contribution guidelines."),
    "requirements.txt": ("dependency", "Python runtime dependencies."),
    "requirements-dev.txt": ("dependency", "Python development dependencies."),
    "package.json": ("dependency", "Node package manifest and scripts."),
    "pyproject.toml": ("config", "Python project metadata and tool configuration."),
    "tsconfig.json": ("config", "TypeScript compiler configuration."),
    "pytest.ini": ("config", "pytest configuration."),
    "Dockerfile": ("build", "Container image definition."),
    "docker-compose.yml": ("build", "Multi-container development stack."),
    "Makefile": ("build", "Task runner entry points."),
    "conftest.py": ("test", "Shared pytest fixtures and hooks."),
}

KNOWN_DIRS: Dict[str, Tuple[str, str]] = {
    ".github": ("ci", "GitHub-specific configuration."),
    ".cursor": ("manifesto", "Cursor editor configuration."),
    ".claude": ("manifesto", "Claude Code project configuration: commands, hooks, and settings."),
    ".vscode": ("config", "Editor workspace settings."),
    "decisions": ("decision", "Machine-readable architecture decision records."),
    "invariants": ("invariant", "Negative invariants that protect historical guards."),
    "maps": ("map", "Repository navigation maps."),
    "personas": ("persona", "Role-specific system prompts for AI workflows."),
    "docs": ("docs", "Long-form documentation."),
    "scripts": ("script", "Command-line tooling and automation scripts."),
    "mcp": ("integration", "Model Context Protocol server and setup guide."),
    "templates": ("template", "Boilerplate to copy into other projects."),
    "tests": ("test", "Automated test suite."),
    "test": ("test", "Automated test suite."),
    "__tests__": ("test", "Automated test suite."),
    "src": ("source", "Application source code."),
    "lib": ("source", "Library source code."),
    "app": ("source", "Application source code."),
    "pkg": ("source", "Reusable packages."),
    "cmd": ("source", "Command entry points."),
    "internal": ("source", "Private application packages."),
    "workflows": ("ci", "CI workflow definitions."),
    "config": ("config", "Configuration files."),
    "public": ("asset", "Static assets served as-is."),
    "static": ("asset", "Static assets."),
    "assets": ("asset", "Static assets."),
    "fixtures": ("data", "Test fixtures and sample data."),
    "migrations": ("source", "Schema or data migrations."),
}

HTTP_METHODS = {"get", "post", "put", "delete", "patch", "head", "options"}
JS_ROUTE_RE = re.compile(
    r"""\b(?:app|router|server|api|fastify|routes?)\.(get|post|put|delete|patch|all|use)\(\s*(['"`])(/[^'"`]*)\2"""
)
NEXT_APP_PAGE_RE = re.compile(r"^(?:.*/)?(?:src/)?app/(?:(.*)/)?page\.(?:tsx|jsx|ts|js)$")
NEXT_APP_ROUTE_RE = re.compile(r"^(?:.*/)?(?:src/)?app/(?:(.*)/)?route\.(?:ts|js)$")
NEXT_PAGES_RE = re.compile(r"^(?:.*/)?(?:src/)?pages/(.+)\.(?:tsx|jsx|ts|js)$")


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
# .agentignore matching (gitignore-style subset)
# --------------------------------------------------------------------------------------
def _glob_to_regex(pattern: str) -> str:
    """Translate one gitignore-style glob into a regular expression fragment."""
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


class IgnoreMatcher:
    """Evaluate ``.agentignore`` rules against repository-relative POSIX paths."""

    def __init__(self, patterns: Iterable[str]) -> None:
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
            line = line.lstrip("/")
            body = _glob_to_regex(line)
            regex = f"^{body}$" if anchored else f"^(?:.*/)?{body}$"
            self._rules.append((re.compile(regex), negate, dir_only))

    @classmethod
    def from_root(cls, root: Path) -> "IgnoreMatcher":
        patterns = list(ALWAYS_IGNORED)
        ignore_file = root / IGNORE_FILE_NAME
        if ignore_file.is_file():
            patterns.extend(ignore_file.read_text(encoding="utf-8", errors="replace").splitlines())
        return cls(patterns)

    def _match_one(self, rel_path: str, is_dir: bool) -> Optional[bool]:
        verdict: Optional[bool] = None
        for regex, negate, dir_only in self._rules:
            if dir_only and not is_dir:
                continue
            if regex.match(rel_path):
                verdict = not negate
        return verdict

    def is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        """Return True if the path, or any parent directory, is ignored."""
        parts = rel_path.strip("/").split("/")
        for depth in range(1, len(parts) + 1):
            prefix = "/".join(parts[:depth])
            as_dir = is_dir if depth == len(parts) else True
            if self._match_one(prefix, as_dir):
                return True
        return False


# --------------------------------------------------------------------------------------
# Scanning
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Entry:
    """One line of the file index. Directories end with ``/``; collapsed ones with ``/**``."""

    path: str
    is_dir: bool
    file_count: int = 0

    @property
    def collapsed(self) -> bool:
        return self.path.endswith("/**")


def scan_tree(root: Path, matcher: IgnoreMatcher) -> List[Entry]:
    """Walk ``root`` and return every non-ignored file and directory."""
    entries: List[Entry] = []
    for dirpath, dirnames, filenames in os.walk(root):
        rel_dir = Path(dirpath).relative_to(root).as_posix()
        prefix = "" if rel_dir == "." else rel_dir + "/"
        kept: List[str] = []
        for name in sorted(dirnames):
            rel = prefix + name
            if matcher.is_ignored(rel, True):
                continue
            if os.path.islink(os.path.join(dirpath, name)):
                entries.append(Entry(rel, False))
                continue
            kept.append(name)
            entries.append(Entry(rel + "/", True))
        dirnames[:] = kept
        for name in sorted(filenames):
            rel = prefix + name
            if not matcher.is_ignored(rel, False):
                entries.append(Entry(rel, False))
    return entries


def ensure_map_entries(entries: List[Entry], root: Path, output: Path, matcher: IgnoreMatcher) -> List[Entry]:
    """Add the map file and its parent directories, which may not exist yet on a first run."""
    try:
        relative = output.resolve().relative_to(root).as_posix()
    except ValueError:
        return entries
    if matcher.is_ignored(relative, False):
        return entries
    known = {e.path for e in entries}
    parts = relative.split("/")
    wanted = ["/".join(parts[:i]) + "/" for i in range(1, len(parts))] + [relative]
    return entries + [Entry(path, path.endswith("/")) for path in wanted if path not in known]


def collapse_large_directories(
    entries: List[Entry], threshold: int, protected: Iterable[str] = ()
) -> List[Entry]:
    """Replace directories that hold more than ``threshold`` direct files by ``dir/**``.

    Directories that already have hand-written rows below them (``protected``) stay expanded.
    """
    if threshold <= 0:
        return entries
    protected_paths = [p for p in protected if not p.endswith("/**")]
    direct_files: Dict[str, int] = {}
    for entry in entries:
        if not entry.is_dir:
            parent = entry.path.rsplit("/", 1)[0] + "/" if "/" in entry.path else ""
            direct_files[parent] = direct_files.get(parent, 0) + 1
    collapsed_dirs = sorted(
        (
            d
            for d, count in direct_files.items()
            if d and count > threshold and not any(p != d and p.startswith(d) for p in protected_paths)
        ),
        key=len,
    )
    accepted: List[str] = []
    for directory in collapsed_dirs:
        if not any(directory.startswith(a) for a in accepted):
            accepted.append(directory)
    if not accepted:
        return entries
    result: List[Entry] = []
    emitted: Set[str] = set()
    for entry in entries:
        owner = next((a for a in accepted if entry.path.startswith(a)), None)
        if owner is None:
            result.append(entry)
        elif owner not in emitted:
            emitted.add(owner)
            total = sum(1 for e in entries if not e.is_dir and e.path.startswith(owner))
            result.append(Entry(owner + "**", True, total))
    return result


def sort_key(entry: Entry) -> Tuple[str, ...]:
    return tuple(entry.path.rstrip("/*").split("/"))


def covers(documented: Iterable[str], path: str) -> bool:
    """Return True if ``path`` is listed directly or covered by a ``dir/**`` entry."""
    documented_set = set(documented)
    if path in documented_set:
        return True
    return any(
        d.endswith("/**") and (path == d[:-2] or path.startswith(d[:-2])) for d in documented_set
    )


# --------------------------------------------------------------------------------------
# Classification and purpose inference
# --------------------------------------------------------------------------------------
def classify(path: str, is_dir: bool) -> str:
    """Assign a category using path, filename, and extension heuristics."""
    clean = path.rstrip("/*")
    parts = clean.split("/")
    name = parts[-1]
    if parts[0] == "templates":
        return "template"
    if not is_dir and name in KNOWN_FILES:
        return KNOWN_FILES[name][0]
    if clean == ".cursor/rules" or clean.startswith(".cursor/rules/"):
        return "manifesto"
    if clean.startswith(".claude/hooks"):
        return "script"
    if parts[0] == ".claude" and name.startswith("settings") and name.endswith(".json"):
        return "config"
    if clean == ".github/copilot-instructions.md":
        return "manifesto"
    if clean.startswith(".github/workflows") or name in {".gitlab-ci.yml", "Jenkinsfile"}:
        return "ci"
    top = parts[0]
    if top in KNOWN_DIRS and (len(parts) > 1 or is_dir):
        category = KNOWN_DIRS[top][0]
        if category not in {"source", "config", "asset", "data"} or is_dir and len(parts) == 1:
            return category
    if is_dir and name in KNOWN_DIRS:
        return KNOWN_DIRS[name][0]
    if is_dir:
        return "directory"
    suffix = Path(name).suffix.lower()
    if re.match(r"^test_.*\.py$", name) or re.match(r".*_test\.(py|go)$", name):
        return "test"
    if re.match(r".*\.(test|spec)\.(ts|tsx|js|jsx|mjs)$", name):
        return "test"
    if any(part in {"tests", "test", "__tests__"} for part in parts[:-1]):
        return "test"
    if suffix in SCRIPT_EXTENSIONS:
        return "script"
    if suffix in DOC_EXTENSIONS:
        return "docs"
    if suffix in CODE_EXTENSIONS:
        return "source"
    if suffix in CONFIG_EXTENSIONS or name.startswith("."):
        return "config"
    if suffix in ASSET_EXTENSIONS:
        return "asset"
    if suffix in DATA_EXTENSIONS:
        return "data"
    return "other"


def _first_comment_line(text: str) -> Optional[str]:
    """Return the first meaningful comment line of a JS/TS/shell file header."""
    for raw in text.splitlines()[:25]:
        line = raw.strip()
        if not line or line.startswith("#!") or line in {"/**", "/*", "*/", "'use strict';", '"use strict";'}:
            continue
        match = re.match(r"^(?://+|#+|/\*+|\*)\s*(?:@fileoverview\s+|@file\s+)?(.+?)\s*(?:\*/)?$", line)
        if match and not match.group(1).startswith("@"):
            return match.group(1)
        return None
    return None


def _first_heading(text: str) -> Optional[str]:
    for raw in text.splitlines()[:40]:
        match = re.match(r"^#\s+(.+?)\s*$", raw)
        if match:
            return match.group(1)
    return None


def _python_docstring(text: str) -> Optional[str]:
    try:
        doc = ast.get_docstring(ast.parse(text))
    except (SyntaxError, ValueError):
        return None
    if not doc:
        return None
    first = doc.strip().splitlines()[0].strip()
    return first or None


def read_text_limited(path: Path) -> Optional[str]:
    """Read a text file up to ``MAX_READ_BYTES``; return None when unreadable or binary."""
    try:
        if path.stat().st_size > MAX_READ_BYTES:
            return None
        data = path.read_bytes()
    except OSError:
        return None
    if b"\x00" in data:
        return None
    return data.decode("utf-8", errors="replace")


def sanitize_cell(text: str, limit: int = MAX_PURPOSE_CHARS) -> str:
    """Make ``text`` safe for a single Markdown table cell."""
    flat = " ".join(text.replace("|", "/").split())
    if len(flat) > limit:
        flat = flat[: limit - 1].rstrip() + "..."
    return flat


def infer_purpose(root: Path, entry: Entry, category: str) -> str:
    """Infer a one-line purpose from the file header, a known name, or the category."""
    path = entry.path
    name = path.rstrip("/*").split("/")[-1]
    if entry.collapsed:
        return f"{entry.file_count} files grouped to save context; open the directory only when needed."
    if entry.is_dir:
        known = KNOWN_DIRS.get(name)
        if known:
            return known[1]
        return f"Directory grouping related {name} files."
    if path == MAP_RELATIVE_PATH:
        return "Index of every path with its category, purpose, and invariants."
    if name in KNOWN_FILES:
        return KNOWN_FILES[name][1]
    text = read_text_limited(root / path)
    suffix = Path(name).suffix.lower()
    found: Optional[str] = None
    if text is not None:
        if suffix in {".py", ".pyi"}:
            found = _python_docstring(text)
        elif suffix in DOC_EXTENSIONS:
            found = _first_heading(text)
        elif suffix in CODE_EXTENSIONS | SCRIPT_EXTENSIONS:
            found = _first_comment_line(text)
        elif suffix in {".yml", ".yaml"}:
            found = _first_comment_line(text) or (re.search(r"^name:\s*(.+)$", text, re.M) or [None, None])[1]
    if found:
        return sanitize_cell(found)
    return sanitize_cell(f"{category.capitalize()} file {name} (auto-generated entry; describe manually).")


# --------------------------------------------------------------------------------------
# Route detection
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Route:
    kind: str
    route: str
    handler: str
    file: str


def _first_string_arg(call: ast.Call) -> Optional[str]:
    if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
        return call.args[0].value
    for keyword in call.keywords:
        if keyword.arg in {"path", "rule"} and isinstance(keyword.value, ast.Constant):
            if isinstance(keyword.value.value, str):
                return keyword.value.value
    return None


def _methods_from_call(call: ast.Call) -> str:
    for keyword in call.keywords:
        if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple, ast.Set)):
            names = [e.value for e in keyword.value.elts if isinstance(e, ast.Constant) and isinstance(e.value, str)]
            if names:
                return "/".join(n.upper() for n in names)
    return "ANY"


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    return (
        isinstance(test, ast.Compare)
        and isinstance(test.left, ast.Name)
        and test.left.id == "__name__"
        and len(test.comparators) == 1
        and isinstance(test.comparators[0], ast.Constant)
        and test.comparators[0].value == "__main__"
    )


def _main_handler(node: ast.If) -> str:
    for child in ast.walk(node):
        if isinstance(child, ast.Call) and isinstance(child.func, ast.Name):
            if child.func.id not in {"exit", "quit", "print"}:
                return f"{child.func.id}()"
    return "module"


def detect_python_routes(path: str, source: str) -> List[Route]:
    """Find HTTP routes, Django URL patterns, and ``__main__`` entry points in Python."""
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError):
        return []
    routes: List[Route] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                if not (isinstance(decorator, ast.Call) and isinstance(decorator.func, ast.Attribute)):
                    continue
                attr = decorator.func.attr
                if attr not in HTTP_METHODS and attr not in {"route", "api_route", "websocket"}:
                    continue
                target = _first_string_arg(decorator)
                if target is None:
                    continue
                kind = attr.upper() if attr in HTTP_METHODS else _methods_from_call(decorator)
                routes.append(Route(kind, target, f"{node.name}()", path))
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id in {"path", "re_path", "url"} and Path(path).name == "urls.py" and len(node.args) >= 2:
                target = _first_string_arg(node)
                if target is not None:
                    routes.append(Route("URL", "/" + target.lstrip("/"), ast.unparse(node.args[1]), path))
    for node in tree.body:
        if isinstance(node, ast.If) and _is_main_guard(node):
            routes.append(Route("CLI", f"python {path}", _main_handler(node), path))
    return routes


def detect_js_routes(path: str, source: str) -> List[Route]:
    """Find Express-style route registrations in JavaScript or TypeScript."""
    return [
        Route(m.group(1).upper(), m.group(3), "-", path) for m in JS_ROUTE_RE.finditer(source)
    ]


def detect_file_based_routes(path: str) -> List[Route]:
    """Detect Next.js style file-system routes from the path alone."""
    def clean(segment: str) -> str:
        parts = [p for p in segment.split("/") if p and not (p.startswith("(") and p.endswith(")"))]
        return "/" + "/".join(parts)

    match = NEXT_APP_PAGE_RE.match(path)
    if match:
        return [Route("PAGE", clean(match.group(1) or ""), "default export", path)]
    match = NEXT_APP_ROUTE_RE.match(path)
    if match:
        return [Route("API", clean(match.group(1) or ""), "route handlers", path)]
    match = NEXT_PAGES_RE.match(path)
    if match:
        slug = match.group(1)
        if slug.rsplit("/", 1)[-1].startswith("_"):
            return []
        slug = re.sub(r"(^|/)index$", "", slug)
        kind = "API" if slug.startswith("api") else "PAGE"
        return [Route(kind, clean(slug), "default export", path)]
    return []


def detect_package_json_routes(path: str, source: str) -> List[Route]:
    """List ``npm run`` scripts and ``bin`` commands from package.json."""
    try:
        data = json.loads(source)
    except ValueError:
        return []
    routes: List[Route] = []
    scripts = data.get("scripts")
    if isinstance(scripts, dict):
        for name, command in scripts.items():
            routes.append(Route("CLI", f"npm run {name}", sanitize_cell(str(command), 60), path))
    bins = data.get("bin")
    if isinstance(bins, dict):
        for name, target in bins.items():
            routes.append(Route("CLI", name, str(target), path))
    elif isinstance(bins, str) and isinstance(data.get("name"), str):
        routes.append(Route("CLI", data["name"], bins, path))
    return routes


def collect_routes(root: Path, entries: Sequence[Entry]) -> List[Route]:
    """Run every route detector over the scanned files."""
    routes: List[Route] = []
    for entry in entries:
        if entry.is_dir or entry.collapsed:
            continue
        suffix = Path(entry.path).suffix.lower()
        routes.extend(detect_file_based_routes(entry.path))
        if suffix not in {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx"} and Path(entry.path).name != "package.json":
            continue
        text = read_text_limited(root / entry.path)
        if text is None:
            continue
        if suffix == ".py":
            routes.extend(detect_python_routes(entry.path, text))
        elif suffix == ".json":
            routes.extend(detect_package_json_routes(entry.path, text))
        else:
            routes.extend(detect_js_routes(entry.path, text))
    seen: Set[Route] = set()
    unique: List[Route] = []
    for route in routes:
        if route not in seen:
            seen.add(route)
            unique.append(route)
    return sorted(unique, key=lambda r: (r.file, r.route, r.kind))


# --------------------------------------------------------------------------------------
# Map parsing and rendering
# --------------------------------------------------------------------------------------
@dataclass
class Row:
    path: str
    category: str
    purpose: str
    invariants: str


_UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")
_PATH_CELL = re.compile(r"^`([^`]+)`$")


def split_row(line: str) -> List[str]:
    """Split a Markdown table row into trimmed cells (``\\|`` stays inside a cell)."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in _UNESCAPED_PIPE.split(stripped)]


def split_sections(text: str) -> List[Tuple[str, List[str]]]:
    """Split Markdown into ``(title, lines)`` pairs on ``## `` headings; title '' is the preamble."""
    sections: List[Tuple[str, List[str]]] = [("", [])]
    for line in text.splitlines():
        match = re.match(r"^##\s+(.+?)\s*$", line)
        if match:
            sections.append((match.group(1), [line]))
        else:
            sections[-1][1].append(line)
    return sections


def parse_file_index(text: str) -> Dict[str, Row]:
    """Parse the ``## File Index`` table into rows keyed by path."""
    rows: Dict[str, Row] = {}
    for title, lines in split_sections(text):
        if not title.lower().startswith(FILE_INDEX_TITLE.lower()):
            continue
        for line in lines:
            if not line.lstrip().startswith("|"):
                continue
            cells = split_row(line)
            if len(cells) < 4:
                continue
            match = _PATH_CELL.match(cells[0])
            if match:
                rows[match.group(1)] = Row(match.group(1), cells[1], cells[2], cells[3])
    return rows


def render_row(row: Row) -> str:
    return f"| `{row.path}` | {row.category} | {row.purpose} | {row.invariants} |"


def render_file_index(rows: Sequence[Row]) -> str:
    lines = [
        f"## {FILE_INDEX_TITLE}",
        "",
        "One row per file or directory. Directories end with `/`; a `dir/**` row covers everything below it.",
        "",
        "| Path | Category | Purpose | Invariants |",
        "| ---- | -------- | ------- | ---------- |",
    ]
    lines.extend(render_row(row) for row in rows)
    return "\n".join(lines) + "\n"


def render_route_table(routes: Sequence[Route]) -> str:
    lines = [f"## {ROUTE_TABLE_TITLE}", ""]
    if not routes:
        lines.append("_No routes or entry points were detected._")
        return "\n".join(lines) + "\n"
    lines.extend(
        [
            "| Kind | Route | Handler | File |",
            "| ---- | ----- | ------- | ---- |",
        ]
    )
    for route in routes:
        lines.append(
            f"| {route.kind} | `{sanitize_cell(route.route, 80)}` | `{sanitize_cell(route.handler, 60)}` | `{route.file}` |"
        )
    return "\n".join(lines) + "\n"


def render_header(project_name: str) -> str:
    legend = "\n".join(f"| `{name}` | {text} |" for name, text in CATEGORY_HELP.items())
    return (
        f"# Project Map: {project_name}\n\n"
        "> Read this file before running exploratory `grep` or `find` commands.\n"
        "> Generated by `scripts/init_mapping.py`; rerun with `--merge` after adding, moving, or deleting files.\n"
        "> Hand-written descriptions and invariant references are preserved by `--merge`.\n\n"
        "## Categories\n\n"
        "| Category | Meaning |\n"
        "| -------- | ------- |\n"
        f"{legend}\n\n"
    )


def build_rows(root: Path, entries: Sequence[Entry], existing: Dict[str, Row]) -> List[Row]:
    """Return one row per entry, reusing hand-written rows where they exist."""
    rows: List[Row] = []
    for entry in sorted(entries, key=sort_key):
        if entry.path in existing:
            rows.append(existing[entry.path])
            continue
        category = classify(entry.path, entry.is_dir)
        rows.append(Row(entry.path, category, infer_purpose(root, entry, category), "-"))
    return rows


def replace_section(text: str, title: str, new_block: str) -> str:
    """Replace a ``## title`` section in ``text`` or append it when missing."""
    sections = split_sections(text)
    for index, (name, _lines) in enumerate(sections):
        if name.lower().startswith(title.lower()):
            sections[index] = (name, new_block.rstrip("\n").splitlines() + [""])
            break
    else:
        sections.append((title, new_block.rstrip("\n").splitlines() + [""]))
    return "\n".join("\n".join(lines) for _name, lines in sections).rstrip("\n") + "\n"


def diff_against_map(entries: Sequence[Entry], existing: Dict[str, Row]) -> Tuple[List[str], List[str]]:
    """Return ``(missing, stale)`` paths comparing the full tree with the documented rows."""
    documented = set(existing)
    missing = [e.path for e in sorted(entries, key=sort_key) if not covers(documented, e.path)]
    actual = {e.path for e in entries}
    stale = sorted(
        p for p in documented if (p[:-2] if p.endswith("/**") else p) not in actual
    )
    return missing, stale


# --------------------------------------------------------------------------------------
# Token-diet statistics
# --------------------------------------------------------------------------------------
def estimate_tokens(text: str) -> int:
    """Approximate token count using the common 1 token ~ 4 characters rule."""
    return len(text) // CHARS_PER_TOKEN


def instruction_files(root: Path) -> List[str]:
    """List agent instruction files present in the repository, including Cursor rules."""
    found = [name for name in INSTRUCTION_FILES if (root / name).is_file()]
    rules = root / ".cursor" / "rules"
    if rules.is_dir():
        found.extend(sorted(f".cursor/rules/{p.name}" for p in rules.iterdir() if p.is_file()))
    return found


def print_stats(style: Style, root: Path, entries: Sequence[Entry], map_text: str) -> None:
    """Print repository size, map size, and the token saving of map-guided reading."""
    sizes: List[Tuple[int, str]] = []
    for entry in entries:
        if entry.is_dir:
            continue
        text = read_text_limited(root / entry.path)
        if text is not None:
            sizes.append((estimate_tokens(text), entry.path))
    if not sizes:
        print(style.yellow("[warn] no readable files found; nothing to measure."))
        return
    ordered = sorted(size for size, _path in sizes)
    middle = len(ordered) // 2
    median = ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) // 2
    whole = sum(ordered)
    largest, largest_path = max(sizes)
    map_tokens = estimate_tokens(map_text)
    rows = len(parse_file_index(map_text))

    def saving(guided: int) -> str:
        return f"{100 * (1 - guided / whole):.1f}% smaller than reading everything"

    print(style.bold("Token diet") + style.dim("  (estimate: 1 token ~ 4 characters)"))
    print(f"  Readable files        {len(sizes):>9,}")
    print(f"  Whole repository      {whole:>9,} tokens")
    print(f"  Project map           {map_tokens:>9,} tokens ({rows} rows)")
    print(f"  Median file           {median:>9,} tokens")
    print(f"  Largest file          {largest:>9,} tokens  {style.dim(largest_path)}")
    print(f"  Map + median file     {map_tokens + median:>9,} tokens  {style.green(saving(map_tokens + median))}")
    print(f"  Map + largest file    {map_tokens + largest:>9,} tokens  {saving(map_tokens + largest)}")
    if map_tokens > MAP_TOKEN_WARNING:
        print(style.yellow(f"[warn] the map is over {MAP_TOKEN_WARNING:,} tokens; group more directories or shorten purposes."))
    if largest * 4 > whole:
        print(style.yellow(f"[warn] {largest_path} is over 25% of the repository; consider splitting it."))

    print()
    print(style.bold("Instruction files") + style.dim(f"  (guidance: keep each under {INSTRUCTION_LINE_LIMIT} lines)"))
    files = instruction_files(root)
    if not files:
        print(style.dim("  none found"))
    for name in files:
        text = read_text_limited(root / name) or ""
        lines = len(text.splitlines())
        status = style.green("ok") if lines <= INSTRUCTION_LINE_LIMIT else style.red("too long")
        print(f"  {name:<36} {lines:>5} lines  ~{estimate_tokens(text):>6,} tokens  {status}")


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="init_mapping.py",
        description="Generate or refresh maps/project-map.md from the directory tree.",
        epilog=(
            "examples:\n"
            "  python scripts/init_mapping.py                 create a new map\n"
            "  python scripts/init_mapping.py --merge         add new files, keep descriptions\n"
            "  python scripts/init_mapping.py --check         CI-friendly freshness check\n"
            "  python scripts/init_mapping.py --stats         token-diet report\n"
            "  python scripts/init_mapping.py --stdout        preview without writing\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--root", default=".", help="repository root to scan (default: current directory)")
    parser.add_argument("--output", help=f"map file to write (default: <root>/{MAP_RELATIVE_PATH})")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--merge", action="store_true", help="update an existing map, preserving hand-written rows")
    mode.add_argument("--force", action="store_true", help="overwrite an existing map from scratch")
    mode.add_argument("--check", action="store_true", help="do not write; exit 1 if the map is out of date")
    mode.add_argument("--stats", action="store_true", help="do not write; report repository size and estimated token savings")
    parser.add_argument("--stdout", action="store_true", help="print the generated map instead of writing it")
    parser.add_argument(
        "--collapse-threshold",
        type=int,
        default=DEFAULT_COLLAPSE_THRESHOLD,
        metavar="N",
        help=f"collapse directories with more than N direct files into one 'dir/**' row (0 disables; default {DEFAULT_COLLAPSE_THRESHOLD})",
    )
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def print_summary(style: Style, rows: Sequence[Row], routes: Sequence[Route]) -> None:
    counts: Dict[str, int] = {}
    for row in rows:
        counts[row.category] = counts.get(row.category, 0) + 1
    print(style.bold("Category summary"))
    for category in sorted(counts, key=lambda c: (-counts[c], c)):
        print(f"  {category:<12} {counts[category]:>4}")
    print(f"  {'routes':<12} {len(routes):>4}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    style = Style(supports_color(sys.stdout) and not args.no_color)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(style.red(f"error: root is not a directory: {root}"), file=sys.stderr)
        return 2
    output = Path(args.output).resolve() if args.output else root / MAP_RELATIVE_PATH

    matcher = IgnoreMatcher.from_root(root)
    all_entries = ensure_map_entries(scan_tree(root, matcher), root, output, matcher)
    existing_text = output.read_text(encoding="utf-8") if output.is_file() else ""
    existing = parse_file_index(existing_text)
    protected = existing.keys() if args.merge else ()
    entries = collapse_large_directories(all_entries, args.collapse_threshold, protected)

    if args.stats:
        if not output.is_file():
            print(style.red(f"error: map not found: {output}"), file=sys.stderr)
            print("       Create it with: python scripts/init_mapping.py", file=sys.stderr)
            return 1
        print_stats(style, root, all_entries, existing_text)
        return 0

    if args.check:
        if not output.is_file():
            print(style.red(f"[FAIL] map not found: {output}"), file=sys.stderr)
            print("       Create it with: python scripts/init_mapping.py", file=sys.stderr)
            return 1
        missing, stale = diff_against_map(all_entries, existing)
        for path in missing:
            print(style.red(f"[FAIL] not in map: {path}"))
        for path in stale:
            print(style.yellow(f"[FAIL] stale map entry (path no longer exists): {path}"))
        if missing or stale:
            print(f"\nRun {style.bold('python scripts/init_mapping.py --merge')} and describe the new rows.")
            return 1
        print(style.green(f"[ok] {output.name} covers all {len(all_entries)} paths."))
        return 0

    if output.is_file() and not (args.merge or args.force or args.stdout):
        print(style.red(f"error: {output} already exists."), file=sys.stderr)
        print("       Use --merge to refresh it or --force to regenerate it.", file=sys.stderr)
        return 1

    rows = build_rows(root, entries, existing if args.merge else {})
    routes = collect_routes(root, entries)
    index_block = render_file_index(rows)
    route_block = render_route_table(routes)

    if args.merge and existing_text:
        document = replace_section(existing_text, FILE_INDEX_TITLE, index_block)
        document = replace_section(document, ROUTE_TABLE_TITLE, route_block)
        missing, stale = diff_against_map(all_entries, existing)
    else:
        document = render_header(root.name) + index_block + "\n" + route_block
        missing, stale = [], []

    if args.stdout:
        sys.stdout.write(document)
        return 0

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(document, encoding="utf-8", newline="\n")
    verb = "Updated" if args.merge and existing_text else "Wrote"
    print(style.green(f"[ok] {verb} {output.relative_to(root) if output.is_relative_to(root) else output}"))
    for path in missing:
        print(f"  {style.cyan('+')} added   {path}  {style.dim('(auto description; please review)')}")
    for path in stale:
        print(f"  {style.yellow('-')} removed {path}")
    print_summary(style, rows, routes)
    return 0


if __name__ == "__main__":
    sys.exit(main())
