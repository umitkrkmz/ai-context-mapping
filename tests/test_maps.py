"""Self-guarding tests: the project map must describe every file and directory.

An agent that trusts ``maps/project-map.md`` is only safe if the map is complete and honest.
These tests fail when:

* a non-ignored file or directory has no row in the map,
* a row points at a path that no longer exists,
* a row is duplicated, malformed, or still carries an auto-generated placeholder,
* ``.agentignore`` hides the map itself, or
* ``CLAUDE.md`` drifts away from ``AGENTS.md``.

The file is intentionally self-contained (standard library plus pytest) so it can be copied
into any project unchanged. Paths ignored by ``.agentignore`` need no map entry.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

import pytest

ROOT = Path(__file__).resolve().parents[1]
MAP_PATH = ROOT / "maps" / "project-map.md"
IGNORE_PATH = ROOT / ".agentignore"
ALWAYS_IGNORED = (".git/", "__pycache__/", ".pytest_cache/")
FILE_INDEX_TITLE = "file index"
PLACEHOLDER = re.compile(r"\b(TODO|TBD|FIXME|XXX)\b|describe manually", re.IGNORECASE)
CATEGORY_PATTERN = re.compile(r"^[a-z][a-z0-9-]*$")
UNESCAPED_PIPE = re.compile(r"(?<!\\)\|")

Row = Tuple[str, str, str, str]


# --------------------------------------------------------------------------------------
# .agentignore handling (gitignore-style subset)
# --------------------------------------------------------------------------------------
def _glob_to_regex(pattern: str) -> str:
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
            body = _glob_to_regex(line.lstrip("/"))
            regex = f"^{body}$" if anchored else f"^(?:.*/)?{body}$"
            self._rules.append((re.compile(regex), negate, dir_only))

    def _verdict(self, rel_path: str, is_dir: bool) -> bool:
        ignored = False
        for regex, negate, dir_only in self._rules:
            if dir_only and not is_dir:
                continue
            if regex.match(rel_path):
                ignored = not negate
        return ignored

    def is_ignored(self, rel_path: str, is_dir: bool) -> bool:
        parts = rel_path.strip("/").split("/")
        for depth in range(1, len(parts) + 1):
            as_dir = is_dir if depth == len(parts) else True
            if self._verdict("/".join(parts[:depth]), as_dir):
                return True
        return False


def load_matcher() -> IgnoreMatcher:
    patterns = list(ALWAYS_IGNORED)
    if IGNORE_PATH.is_file():
        patterns.extend(IGNORE_PATH.read_text(encoding="utf-8", errors="replace").splitlines())
    return IgnoreMatcher(patterns)


# --------------------------------------------------------------------------------------
# Repository and map readers
# --------------------------------------------------------------------------------------
def walk_repository() -> List[str]:
    """Return every non-ignored path; directories carry a trailing slash."""
    matcher = load_matcher()
    found: List[str] = []
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel_dir = Path(dirpath).relative_to(ROOT).as_posix()
        prefix = "" if rel_dir == "." else rel_dir + "/"
        kept: List[str] = []
        for name in sorted(dirnames):
            rel = prefix + name
            if matcher.is_ignored(rel, True):
                continue
            if os.path.islink(os.path.join(dirpath, name)):
                found.append(rel)
                continue
            kept.append(name)
            found.append(rel + "/")
        dirnames[:] = kept
        for name in sorted(filenames):
            rel = prefix + name
            if not matcher.is_ignored(rel, False):
                found.append(rel)
    return found


def split_row(line: str) -> List[str]:
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|") and not stripped.endswith("\\|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in UNESCAPED_PIPE.split(stripped)]


def read_rows() -> List[Row]:
    """Parse every row of the ``## File Index`` table, preserving duplicates."""
    rows: List[Row] = []
    in_index = False
    for line in MAP_PATH.read_text(encoding="utf-8").splitlines():
        heading = re.match(r"^##\s+(.+?)\s*$", line)
        if heading:
            in_index = heading.group(1).lower().startswith(FILE_INDEX_TITLE)
            continue
        if not in_index or not line.lstrip().startswith("|"):
            continue
        cells = split_row(line)
        if len(cells) < 4:
            continue
        match = re.match(r"^`([^`]+)`$", cells[0])
        if match:
            rows.append((match.group(1), cells[1], cells[2], cells[3]))
    return rows


def is_documented(path: str, documented: Set[str]) -> bool:
    """True when ``path`` has its own row or sits under a ``dir/**`` group row."""
    if path in documented:
        return True
    return any(d.endswith("/**") and (path == d[:-2] or path.startswith(d[:-2])) for d in documented)


@pytest.fixture(scope="module")
def rows() -> List[Row]:
    assert MAP_PATH.is_file(), "maps/project-map.md is missing. Create it with: python scripts/init_mapping.py"
    return read_rows()


# --------------------------------------------------------------------------------------
# Tests
# --------------------------------------------------------------------------------------
def test_map_has_file_index_rows(rows: List[Row]) -> None:
    assert rows, "maps/project-map.md has no rows under the '## File Index' heading"


def test_every_non_ignored_path_is_documented(rows: List[Row]) -> None:
    documented = {row[0] for row in rows}
    missing = [path for path in walk_repository() if not is_documented(path, documented)]
    assert not missing, (
        "These paths exist but have no entry in maps/project-map.md:\n  "
        + "\n  ".join(missing)
        + "\nAdd them with: python scripts/init_mapping.py --merge  (then describe each new row)."
    )


def test_map_has_no_stale_entries(rows: List[Row]) -> None:
    stale: List[str] = []
    for path, _category, _purpose, _invariants in rows:
        target = path[:-3] if path.endswith("/**") else path
        if not (ROOT / target.rstrip("/")).exists():
            stale.append(path)
    assert not stale, (
        "These map entries point at paths that no longer exist:\n  "
        + "\n  ".join(stale)
        + "\nRemove them, or run: python scripts/init_mapping.py --merge"
    )


def test_map_entries_are_unique(rows: List[Row]) -> None:
    seen: Dict[str, int] = {}
    for path, *_rest in rows:
        seen[path] = seen.get(path, 0) + 1
    duplicates = sorted(path for path, count in seen.items() if count > 1)
    assert not duplicates, "Duplicate map entries: " + ", ".join(duplicates)


def test_map_entries_are_well_formed(rows: List[Row]) -> None:
    problems: List[str] = []
    for path, category, purpose, invariants in rows:
        if "\\" in path or path.startswith(("./", "/")) or "//" in path:
            problems.append(f"{path}: use a repository-relative POSIX path without './' or a leading '/'")
        if not CATEGORY_PATTERN.match(category):
            problems.append(f"{path}: category {category!r} must be a lowercase word such as 'source' or 'test'")
        if len(purpose) < 8:
            problems.append(f"{path}: purpose is too short to be useful")
        if PLACEHOLDER.search(purpose):
            problems.append(f"{path}: purpose still contains a placeholder ({purpose!r})")
        if not invariants:
            problems.append(f"{path}: invariants cell is empty; write '-' when none apply")
    assert not problems, "Malformed map rows:\n  " + "\n  ".join(problems)


def test_agentignore_does_not_hide_the_map() -> None:
    matcher = load_matcher()
    for path in ("maps/project-map.md", "AGENTS.md"):
        if (ROOT / path).exists():
            assert not matcher.is_ignored(path, False), f".agentignore must not ignore {path}"


def test_claude_md_mirrors_agents_md() -> None:
    agents, claude = ROOT / "AGENTS.md", ROOT / "CLAUDE.md"
    if not (agents.exists() and claude.exists()):
        pytest.skip("AGENTS.md and CLAUDE.md are not both present")
    if claude.is_symlink() and claude.resolve() == agents.resolve():
        return

    def normalized(path: Path) -> bytes:
        return path.read_bytes().replace(b"\r\n", b"\n")

    assert normalized(claude) == normalized(agents), (
        "CLAUDE.md differs from AGENTS.md. Edit AGENTS.md, then copy it over CLAUDE.md."
    )
