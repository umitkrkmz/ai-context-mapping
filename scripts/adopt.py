#!/usr/bin/env python3
"""Install the AI-context-mapping framework into another project.

This automates the README quickstart. Run it from a copy of this repository (or the Claude Code
plugin), pointing ``--target`` at your project:

    python scripts/adopt.py --target ../my-project --stack python --agent claude --agent cursor

It copies the guardrail scripts, the MCP server, the invariant and decision documents, the personas,
``.agentignore``, and the stack's ``AGENTS.md`` and map test into the target. Then it writes the
entry file for each agent you name and generates ``maps/project-map.md`` for the whole project.

Safety rules (AGENTS.md Rule 3):

* An existing file is never overwritten. It is reported as skipped, so you can merge it by hand.
* An existing map is never regenerated. Refresh it yourself with ``init_mapping.py --merge``.
* ``--dry-run`` prints the plan and writes nothing.
* Nothing is executed: no git hook, no ``pip install``, no subprocess (invariant NI-002). The
  report ends with the commands to run next.

What it deliberately leaves out:

* ADR-0001 (no database) is this repository's own decision, so only ``decisions/README.md`` is
  copied. Write your project's decisions there.
* The Rule 1 map gate is opt-in. In Claude Code, enable it through the plugin's ``map_gate`` option.

Exit codes: 0 done (or planned with --dry-run), 2 usage error (bad target, unknown stack or agent).

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
FRAMEWORK_ROOT = Path(__file__).resolve().parent.parent
STACKS = ("python", "typescript", "generic")
AGENTS = ("claude", "cursor", "copilot", "codex")
MAP_RELATIVE_PATH = "maps/project-map.md"

# (source relative to the framework, destination relative to the target), copied for every stack.
COMMON_FILES: Tuple[Tuple[str, str], ...] = (
    ("scripts/init_mapping.py", "scripts/init_mapping.py"),
    ("scripts/verify_invariants.py", "scripts/verify_invariants.py"),
    ("scripts/check_dependency_budget.py", "scripts/check_dependency_budget.py"),
    ("scripts/mutation_guard.py", "scripts/mutation_guard.py"),
    ("scripts/install_hooks.sh", "scripts/install_hooks.sh"),
    ("mcp/context_server.py", "mcp/context_server.py"),
    ("mcp/README.md", "mcp/README.md"),
    # The adopter version: this repository's own file also guards its Claude Code hooks (NI-010) and
    # benchmark harness, which an adopted project does not have.
    ("templates/invariants/negative-invariants.md", "invariants/negative-invariants.md"),
    ("decisions/README.md", "decisions/README.md"),
    ("personas/refactorer.md", "personas/refactorer.md"),
    ("personas/tester.md", "personas/tester.md"),
    ("personas/ux_architect.md", "personas/ux_architect.md"),
    (".agentignore", ".agentignore"),
)

STACK_FILES: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "python": (
        ("templates/python/AGENTS.md", "AGENTS.md"),
        ("templates/python/tests/test_maps.py", "tests/test_maps.py"),
    ),
    "typescript": (
        ("templates/typescript/AGENTS.md", "AGENTS.md"),
        ("templates/typescript/tests/test_maps.test.ts", "tests/test_maps.test.ts"),
    ),
    "generic": (("templates/generic/AGENTS.md", "AGENTS.md"),),
}

# Claude Code gets CLAUDE.md, a byte-identical copy of the stack's AGENTS.md (see plan()).
# Codex reads AGENTS.md natively, so it needs no entry file of its own.
AGENT_FILES: Dict[str, Tuple[Tuple[str, str], ...]] = {
    "claude": (),
    "cursor": ((".cursor/rules/context-guardrails.mdc", ".cursor/rules/context-guardrails.mdc"),),
    "copilot": ((".github/copilot-instructions.md", ".github/copilot-instructions.md"),),
    "codex": (),
}

CI_FILE = ("templates/ci/ai-guardrails.yml", ".github/workflows/ai-guardrails.yml")


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

    def green(self, text: str) -> str:
        return self._wrap("32", text)

    def yellow(self, text: str) -> str:
        return self._wrap("33", text)

    def red(self, text: str) -> str:
        return self._wrap("31", text)


# --------------------------------------------------------------------------------------
# Planning and copying
# --------------------------------------------------------------------------------------
@dataclass
class Step:
    source: Path
    destination: str  # relative to the target, POSIX form

    def target_path(self, target: Path) -> Path:
        return target / self.destination


class AdoptError(Exception):
    """A usage problem (exit code 2)."""


def plan(stack: str, agents: Sequence[str], with_ci: bool, framework: Path = FRAMEWORK_ROOT) -> List[Step]:
    """Return the copy steps for one adoption, in order, without touching the disk."""
    if stack not in STACKS:
        raise AdoptError(f"unknown stack '{stack}'; choose one of: {', '.join(STACKS)}")
    unknown = [a for a in agents if a not in AGENTS]
    if unknown:
        raise AdoptError(f"unknown agent(s) {unknown}; choose from: {', '.join(AGENTS)}")
    pairs = list(COMMON_FILES) + list(STACK_FILES[stack])
    stack_manifesto = STACK_FILES[stack][0][0]
    for agent in dict.fromkeys(agents):  # keep order, drop duplicates
        if agent == "claude":
            pairs.append((stack_manifesto, "CLAUDE.md"))
        pairs.extend(AGENT_FILES[agent])
    if with_ci:
        pairs.append(CI_FILE)
    steps = [Step(framework / source, destination) for source, destination in pairs]
    missing = [str(s.source) for s in steps if not s.source.is_file()]
    if missing:
        raise AdoptError(f"the framework copy is incomplete; missing: {', '.join(missing)}")
    return steps


def copy_file(source: Path, destination: Path) -> None:
    """Copy bytes exactly (CLAUDE.md must stay byte-identical to AGENTS.md); never overwrite."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "xb") as handle:  # "x" fails if the file appeared since planning
        handle.write(source.read_bytes())


def load_init_mapping(framework: Path) -> Callable[[Sequence[str]], int]:
    """Import the framework's init_mapping.py in-process and return its ``main``."""
    path = framework / "scripts" / "init_mapping.py"
    spec = importlib.util.spec_from_file_location("init_mapping", path)
    if spec is None or spec.loader is None:
        raise AdoptError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["init_mapping"] = module  # dataclasses resolve annotations through sys.modules
    spec.loader.exec_module(module)
    return module.main


def next_steps(stack: str, agents: Sequence[str], wrote_map: bool) -> List[str]:
    lines = []
    if wrote_map:
        lines.append(f"Describe every row in {MAP_RELATIVE_PATH} that ends with 'describe manually'.")
    else:
        lines.append("Refresh the map: python scripts/init_mapping.py --merge, then describe the new rows.")
    lines.append("Review invariants/negative-invariants.md: keep the rules that fit, then add your own.")
    if stack == "python":
        lines.append("Run the map test: python -m pytest -q tests/test_maps.py")
    elif stack == "typescript":
        lines.append("Run the map test with your runner, for example: npx vitest run tests/test_maps.test.ts")
    lines.append("Check the rules: python scripts/verify_invariants.py")
    lines.append("Run the checks on every commit: sh scripts/install_hooks.sh")
    if "claude" in agents:
        lines.append("Claude Code: install the plugin for hooks, skills, and the MCP server (see the README).")
    if "cursor" in agents or "codex" in agents:
        lines.append("Cursor and Codex: connect the MCP server with the config in mcp/README.md.")
    return lines


def adopt(target: Path, stack: str, agents: Sequence[str], with_ci: bool, dry_run: bool,
          framework: Path = FRAMEWORK_ROOT, style: Optional[Style] = None) -> int:
    """Copy the framework into ``target`` and generate its map. Returns an exit code."""
    style = style or Style(False)
    target = target.resolve()
    if not target.is_dir():
        raise AdoptError(f"target is not a directory: {target}")
    if target == framework.resolve():
        raise AdoptError("the target is the framework repository itself; point --target at your project")
    steps = plan(stack, agents, with_ci, framework)

    print(style.bold(f"{'Plan for' if dry_run else 'Adopting into'} {target}") + f"  (stack: {stack})")
    copied = skipped = 0
    for step in steps:
        destination = step.target_path(target)
        if destination.exists():
            print(f"  {style.yellow('skip')}  {step.destination}  (exists; merge it by hand if needed)")
            skipped += 1
            continue
        if not dry_run:
            copy_file(step.source, destination)
        print(f"  {style.green('add ')}  {step.destination}")
        copied += 1

    map_path = target / MAP_RELATIVE_PATH
    wrote_map = not map_path.exists()
    if not wrote_map:
        print(f"  {style.yellow('skip')}  {MAP_RELATIVE_PATH}  (exists; not regenerated)")
    elif dry_run:
        print(f"  {style.green('add ')}  {MAP_RELATIVE_PATH}  (generated from the project tree)")
    else:
        status = load_init_mapping(framework)(["--root", str(target), "--no-color"])
        if status != 0:
            print(style.red(f"init_mapping.py exited {status}; the map was not written."), file=sys.stderr)
            return status

    verb = "Would add" if dry_run else "Added"
    generated = f"; {'would generate' if dry_run else 'generated'} {MAP_RELATIVE_PATH}" if wrote_map else ""
    print(f"\n{verb} {copied} file(s), skipped {skipped}{generated}.")
    print(style.bold("Next steps:"))
    for number, line in enumerate(next_steps(stack, agents, wrote_map), start=1):
        print(f"  {number}. {line}")
    return 0


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="adopt.py",
        description="Install the AI-context-mapping guardrails into another project. Never overwrites files.",
        epilog=(
            "examples:\n"
            "  python scripts/adopt.py --target ../app --dry-run              show the plan\n"
            "  python scripts/adopt.py --target ../app --agent claude         Python project, Claude Code\n"
            "  python scripts/adopt.py --target ../web --stack typescript --agent cursor --agent copilot --ci\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--target", default=".", help="project root to install into (default: current directory)")
    parser.add_argument("--stack", default="python", choices=STACKS, help="template set (default: python)")
    parser.add_argument("--agent", action="append", default=[], choices=AGENTS,
                        help="write this agent's entry file; repeatable (codex reads AGENTS.md as is)")
    parser.add_argument("--ci", action="store_true", help="also add .github/workflows/ai-guardrails.yml")
    parser.add_argument("--dry-run", action="store_true", help="print the plan and write nothing")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    style = Style(supports_color(sys.stdout) and not args.no_color)
    try:
        return adopt(Path(args.target), args.stack, args.agent, args.ci, args.dry_run, style=style)
    except AdoptError as exc:
        print(style.red(f"error: {exc}"), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
