#!/usr/bin/env python3
"""Audit dependency manifests against an approved list and a package-count ceiling.

AGENTS.md Rule 4 says: zero unauthorized third-party dependencies. This tool makes that rule
enforceable. It reads ``requirements*.txt`` (following ``-r`` includes), ``package.json``,
and ``pyproject.toml`` (Python 3.11+), then fails with exit code 1 when:

* a dependency is not on the approved list, or
* the number of dependencies exceeds the configured ceiling.

Configuration is optional. Without any, a project that declares no dependencies passes and
any declared dependency is only counted. Provide limits with a JSON file
(``.dependency-budget.json`` in the root is picked up automatically) or CLI flags:

    {
      "approved": ["requests", "flask*"],
      "approved_dev": ["pytest*", "@types/*"],
      "max_dependencies": 5,
      "max_dev_dependencies": 10
    }

``approved`` and ``approved_dev`` accept ``fnmatch`` wildcards. When ``approved`` is present
(even as an empty list) every runtime dependency must match it. Development dependencies are
restricted only when ``approved_dev`` is present.

Exit codes: 0 within budget, 1 budget violation, 2 configuration or parse error.

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Set, Tuple

VERSION = "1.0.0"
CONFIG_FILE = ".dependency-budget.json"
DEV_HINTS = ("dev", "test", "lint", "doc", "ci", "typing", "build")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "env", "__pycache__", "dist", "build", ".tox"}
EXAMPLE_CONFIG = {
    "approved": ["requests", "flask*"],
    "approved_dev": ["pytest*", "@types/*"],
    "max_dependencies": 5,
    "max_dev_dependencies": 10,
}


class BudgetError(Exception):
    """A configuration or parsing problem (exit code 2)."""


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


# --------------------------------------------------------------------------------------
# Manifest parsing
# --------------------------------------------------------------------------------------
@dataclass(frozen=True)
class Dependency:
    name: str
    spec: str
    group: str  # "runtime" or "dev"
    source: str


def normalize_python_name(name: str) -> str:
    """PEP 503 normalization so ``Flask_SQLAlchemy`` equals ``flask-sqlalchemy``."""
    return re.sub(r"[-_.]+", "-", name).lower()


_REQ_NAME = re.compile(r"^([A-Za-z0-9](?:[A-Za-z0-9._-]*[A-Za-z0-9])?)\s*(?:\[[^\]]*\])?\s*(.*)$")
_EGG = re.compile(r"[#&]egg=([A-Za-z0-9._-]+)")


def parse_requirement(line: str) -> Optional[Tuple[str, str]]:
    """Return ``(name, version_spec)`` for one requirement line, or None for non-packages."""
    text = line.strip()
    if not text:
        return None
    egg = _EGG.search(text)
    if egg:
        return egg.group(1), text.split("#egg=")[0].strip()
    if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", text) or text.startswith(("git+", "./", "../", "/")):
        tail = re.split(r"[/\\]", text.split("#")[0].rstrip("/\\"))[-1]
        tail = re.sub(r"\.(git|zip|tar\.gz|whl)$", "", tail)
        return (tail, text) if tail else None
    text = text.split(";")[0].strip()
    if "@" in text and not text.startswith("@"):
        name = text.split("@")[0].strip()
        match = _REQ_NAME.match(name)
        return (match.group(1), "@ " + text.split("@", 1)[1].strip()) if match else None
    match = _REQ_NAME.match(text)
    if not match:
        return None
    return match.group(1), match.group(2).strip()


def read_requirements(path: Path, group: str, seen: Optional[Set[Path]] = None) -> List[Dependency]:
    """Parse a requirements file, following ``-r``/``--requirement`` includes."""
    seen = seen if seen is not None else set()
    resolved = path.resolve()
    if resolved in seen:
        return []
    seen.add(resolved)
    try:
        raw_lines = path.read_text(encoding="utf-8-sig").splitlines()
    except OSError as exc:
        raise BudgetError(f"cannot read {path}: {exc}") from exc
    joined: List[str] = []
    buffer = ""
    for raw in raw_lines:
        piece = raw.rstrip()
        if piece.endswith("\\"):
            buffer += piece[:-1] + " "
            continue
        joined.append(buffer + piece)
        buffer = ""
    if buffer:
        joined.append(buffer)

    found: List[Dependency] = []
    for line in joined:
        text = re.sub(r"(^|\s)#.*$", "", line).strip()
        if not text:
            continue
        include = re.match(r"^(?:-r|--requirement)[\s=]+(\S+)", text)
        if include:
            target = (path.parent / include.group(1)).resolve()
            if target.is_file():
                included_group = "dev" if _looks_dev(target.stem) else group
                found.extend(read_requirements(target, included_group, seen))
            continue
        editable = re.match(r"^(?:-e|--editable)[\s=]+(.+)$", text)
        if editable:
            text = editable.group(1).strip()
        elif text.startswith("-"):
            continue
        text = re.sub(r"\s--hash[=\s]\S+", "", text).strip()
        parsed = parse_requirement(text)
        if parsed:
            name, spec = parsed
            found.append(Dependency(normalize_python_name(name), spec, group, path.name))
    return found


def read_package_json(path: Path) -> List[Dependency]:
    """Parse ``dependencies``, ``optionalDependencies`` and ``devDependencies``."""
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as exc:
        raise BudgetError(f"cannot parse {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise BudgetError(f"{path} must contain a JSON object")
    found: List[Dependency] = []
    for key, group in (("dependencies", "runtime"), ("optionalDependencies", "runtime"), ("devDependencies", "dev")):
        section = data.get(key, {})
        if not isinstance(section, dict):
            raise BudgetError(f"{path}: '{key}' must be an object")
        for name, spec in section.items():
            found.append(Dependency(name.lower(), str(spec), group, path.name))
    return found


def read_pyproject(path: Path, warnings: List[str]) -> List[Dependency]:
    """Parse PEP 621 dependencies and dependency groups (needs ``tomllib``, Python 3.11+)."""
    try:
        import tomllib  # type: ignore[import-not-found]
    except ImportError:
        warnings.append(f"{path.name}: skipped; reading TOML needs Python 3.11+ (found {sys.version_info.major}.{sys.version_info.minor})")
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise BudgetError(f"cannot parse {path}: {exc}") from exc

    def convert(items: Any, group: str) -> List[Dependency]:
        result: List[Dependency] = []
        for item in items if isinstance(items, list) else []:
            parsed = parse_requirement(item) if isinstance(item, str) else None
            if parsed:
                result.append(Dependency(normalize_python_name(parsed[0]), parsed[1], group, path.name))
        return result

    project = data.get("project", {}) if isinstance(data.get("project"), dict) else {}
    found = convert(project.get("dependencies"), "runtime")
    for extra, items in (project.get("optional-dependencies") or {}).items():
        found.extend(convert(items, "dev" if _looks_dev(extra) else "runtime"))
    for group_name, items in (data.get("dependency-groups") or {}).items():
        found.extend(convert(items, "dev" if _looks_dev(group_name) else "runtime"))
    return found


def _looks_dev(name: str) -> bool:
    lowered = name.lower()
    return any(hint in lowered for hint in DEV_HINTS)


def _scan_directory(directory: Path, any_txt: bool) -> List[Path]:
    """List manifest files that live directly in ``directory``."""
    found: List[Path] = []
    for name in sorted(os.listdir(directory)):
        path = directory / name
        if not path.is_file():
            continue
        if name in {"package.json", "pyproject.toml"}:
            found.append(path)
        elif re.match(r"^requirements.*\.txt$", name) or (any_txt and name.endswith(".txt")):
            found.append(path)
        elif re.match(r"^requirements.*\.in$", name) and not path.with_suffix(".txt").exists():
            found.append(path)
    return found


def discover_manifests(root: Path, recursive: bool) -> List[Path]:
    """Find manifest files under ``root`` (top level and ``requirements/`` unless ``recursive``)."""
    if not recursive:
        manifests = _scan_directory(root, False)
        if (root / "requirements").is_dir():
            manifests.extend(_scan_directory(root / "requirements", True))
        return manifests
    manifests = []
    for directory, dirnames, _files in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS and not d.endswith(".egg-info"))
        base = Path(directory)
        manifests.extend(_scan_directory(base, base.name == "requirements"))
    return manifests


def collect(paths: Sequence[Path], warnings: List[str]) -> List[Dependency]:
    dependencies: List[Dependency] = []
    for path in paths:
        if path.name == "package.json":
            dependencies.extend(read_package_json(path))
        elif path.name == "pyproject.toml":
            dependencies.extend(read_pyproject(path, warnings))
        else:
            group = "dev" if _looks_dev(path.stem) else "runtime"
            dependencies.extend(read_requirements(path, group))
    return dependencies


# --------------------------------------------------------------------------------------
# Budget evaluation
# --------------------------------------------------------------------------------------
@dataclass
class Budget:
    approved: Optional[List[str]] = None
    approved_dev: Optional[List[str]] = None
    max_dependencies: Optional[int] = None
    max_dev_dependencies: Optional[int] = None


def load_budget(config_path: Optional[Path], args: argparse.Namespace) -> Budget:
    """Merge the JSON config (if any) with CLI overrides."""
    budget = Budget()
    if config_path is not None:
        try:
            data = json.loads(config_path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise BudgetError(f"cannot read config {config_path}: {exc}") from exc
        if not isinstance(data, dict):
            raise BudgetError(f"{config_path} must contain a JSON object")
        unknown = set(data) - set(EXAMPLE_CONFIG)
        if unknown:
            raise BudgetError(f"{config_path}: unknown key(s) {sorted(unknown)}; allowed: {sorted(EXAMPLE_CONFIG)}")
        for key in ("approved", "approved_dev"):
            if key in data:
                if not isinstance(data[key], list) or not all(isinstance(v, str) for v in data[key]):
                    raise BudgetError(f"{config_path}: '{key}' must be a list of strings")
                setattr(budget, key, list(data[key]))
        for key in ("max_dependencies", "max_dev_dependencies"):
            if key in data:
                if not isinstance(data[key], int) or isinstance(data[key], bool) or data[key] < 0:
                    raise BudgetError(f"{config_path}: '{key}' must be a non-negative integer")
                setattr(budget, key, data[key])
    if args.approved is not None:
        budget.approved = [p.strip() for p in args.approved.split(",") if p.strip()]
    if args.approved_dev is not None:
        budget.approved_dev = [p.strip() for p in args.approved_dev.split(",") if p.strip()]
    if args.max is not None:
        budget.max_dependencies = args.max
    if args.max_dev is not None:
        budget.max_dev_dependencies = args.max_dev
    return budget


def is_approved(name: str, patterns: Sequence[str]) -> bool:
    """Match a package name against approved patterns (Python names are PEP 503 normalized)."""
    lowered = name.lower()
    for pattern in patterns:
        candidates = {pattern.lower(), normalize_python_name(pattern)}
        if any(fnmatch.fnmatchcase(lowered, candidate) for candidate in candidates):
            return True
    return False


def evaluate(dependencies: Sequence[Dependency], budget: Budget) -> Tuple[List[str], Dict[str, int]]:
    """Return ``(violation_messages, counts_by_group)``."""
    unique: Dict[Tuple[str, str], Dependency] = {}
    for dependency in dependencies:
        unique.setdefault((dependency.group, dependency.name), dependency)
    counts = {"runtime": 0, "dev": 0}
    violations: List[str] = []
    for (group, name), dependency in sorted(unique.items()):
        counts[group] += 1
        patterns = budget.approved if group == "runtime" else budget.approved_dev
        if patterns is not None and not is_approved(name, patterns):
            label = "dependency" if group == "runtime" else "dev dependency"
            violations.append(f"unapproved {label} '{name}' ({dependency.spec or 'any version'}) in {dependency.source}")
    for group, limit, label in (
        ("runtime", budget.max_dependencies, "dependencies"),
        ("dev", budget.max_dev_dependencies, "dev dependencies"),
    ):
        if limit is not None and counts[group] > limit:
            violations.append(f"{counts[group]} {label} exceed the budget of {limit}")
    return violations, counts


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="check_dependency_budget.py",
        description="Fail when dependencies are unapproved or exceed the package-count ceiling.",
        epilog=(
            "examples:\n"
            "  python scripts/check_dependency_budget.py\n"
            "  python scripts/check_dependency_budget.py --approved requests,flask --max 5\n"
            "  python scripts/check_dependency_budget.py --config ci/deps.json requirements.txt\n"
            "  python scripts/check_dependency_budget.py --print-example-config > .dependency-budget.json\n\n"
            "exit codes: 0 within budget, 1 violation, 2 configuration or parse error"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("files", nargs="*", help="manifest files to audit (default: discover in the root)")
    parser.add_argument("--root", default=".", help="repository root (default: current directory)")
    parser.add_argument("--config", help=f"JSON budget file (default: <root>/{CONFIG_FILE} when present)")
    parser.add_argument("--approved", help="comma-separated approved runtime packages (wildcards allowed)")
    parser.add_argument("--approved-dev", help="comma-separated approved development packages")
    parser.add_argument("--max", type=int, metavar="N", help="maximum number of runtime dependencies")
    parser.add_argument("--max-dev", type=int, metavar="N", help="maximum number of development dependencies")
    parser.add_argument("--recursive", action="store_true", help="also discover manifests in subdirectories (monorepos)")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="output format (default: text)")
    parser.add_argument("--print-example-config", action="store_true", help="print a sample budget file and exit")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    style = Style(supports_color(sys.stdout) and not args.no_color)
    if args.print_example_config:
        print(json.dumps(EXAMPLE_CONFIG, indent=2))
        return 0
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(style.red(f"error: root is not a directory: {root}"), file=sys.stderr)
        return 2

    warnings: List[str] = []
    try:
        config_path = Path(args.config) if args.config else (root / CONFIG_FILE if (root / CONFIG_FILE).is_file() else None)
        budget = load_budget(config_path, args)
        if args.files:
            manifests = [Path(f) if os.path.isabs(f) else root / f for f in args.files]
            for manifest in manifests:
                if not manifest.is_file():
                    raise BudgetError(f"manifest not found: {manifest}")
        else:
            manifests = discover_manifests(root, args.recursive)
        dependencies = collect(manifests, warnings)
    except BudgetError as exc:
        print(style.red(f"error: {exc}"), file=sys.stderr)
        return 2

    violations, counts = evaluate(dependencies, budget)

    if args.format == "json":
        print(
            json.dumps(
                {
                    "ok": not violations,
                    "manifests": [m.relative_to(root).as_posix() if m.is_relative_to(root) else str(m) for m in manifests],
                    "counts": counts,
                    "violations": violations,
                    "warnings": warnings,
                    "dependencies": [d.__dict__ for d in dependencies],
                },
                indent=2,
            )
        )
        return 1 if violations else 0

    print(style.bold("Dependency budget"))
    if not manifests:
        print(style.dim("  no dependency manifests found"))
    for manifest in manifests:
        shown = manifest.relative_to(root).as_posix() if manifest.is_relative_to(root) else str(manifest)
        print(style.dim(f"  manifest: {shown}"))
    ceiling = lambda limit: "unlimited" if limit is None else str(limit)  # noqa: E731
    print(f"  runtime: {counts['runtime']} (ceiling {ceiling(budget.max_dependencies)})   dev: {counts['dev']} (ceiling {ceiling(budget.max_dev_dependencies)})")
    for warning in warnings:
        print(style.yellow(f"[warn] {warning}"))
    for message in violations:
        print(style.red("[FAIL]") + f" {message}")
    if violations:
        print("\nDo not add dependencies without the user's approval (AGENTS.md Rule 4).")
        print("If approved, add the package to the approved list in your budget file in the same commit.")
        return 1
    print(style.green("[ok] dependency budget respected."))
    return 0


if __name__ == "__main__":
    sys.exit(main())
