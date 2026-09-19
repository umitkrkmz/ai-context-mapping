#!/usr/bin/env python3
"""Prove that a regression test actually guards a function by breaking the function.

A green test suite is only evidence when it can turn red. This tool takes a test path and a
target function, runs the tests once unmodified (they must pass), then temporarily rewrites
the target's source with mutants -- inverted comparisons, swapped operators, flipped
booleans, dropped return values, and finally a version that does nothing at all -- and
runs the tests again for each mutant. A mutant is *killed* when the tests fail.

Verdict:
    FAIL  the "neutralize" mutant survived: the tests stay green even when the function
          does nothing, so they are mocked, unrelated, or asserting nothing.
    FAIL  the kill ratio is below ``--min-score`` (default 0.5).
    PASS  otherwise.

Safety: the original file is backed up next to the target (``<file>.mgbak``) and restored
in a ``finally`` block, on SIGINT/SIGTERM, and at interpreter exit. If the process is
killed without a chance to clean up, rerun with ``--recover``.

Target syntax:   path/to/module.py:function_name   or   path/to/module.py:Class.method
Only Python targets are mutated. The test runner may be anything (default: pytest); use
``--runner "npx vitest run {test}"`` style commands for other stacks that exercise Python.

Exit codes: 0 pass, 1 verification failed, 2 usage or environment error.

Standard library only. Python 3.9+.
"""
from __future__ import annotations

import argparse
import ast
import atexit
import copy
import json
import os
import shlex
import signal
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

VERSION = "1.0.0"
BACKUP_SUFFIX = ".mgbak"
KINDS = ("compare", "arith", "bool", "not", "if", "return", "const")
DEFAULT_MIN_SCORE = 0.5
DEFAULT_MAX_MUTANTS = 30
DEFAULT_TIMEOUT = 120

COMPARE_SWAPS: Dict[type, type] = {
    ast.Eq: ast.NotEq, ast.NotEq: ast.Eq, ast.Lt: ast.GtE, ast.LtE: ast.Gt,
    ast.Gt: ast.LtE, ast.GtE: ast.Lt, ast.Is: ast.IsNot, ast.IsNot: ast.Is,
    ast.In: ast.NotIn, ast.NotIn: ast.In,
}
ARITH_SWAPS: Dict[type, type] = {
    ast.Add: ast.Sub, ast.Sub: ast.Add, ast.Mult: ast.Div, ast.Div: ast.Mult,
    ast.FloorDiv: ast.Mult, ast.Mod: ast.Mult, ast.Pow: ast.Mult,
    ast.BitAnd: ast.BitOr, ast.BitOr: ast.BitAnd, ast.BitXor: ast.BitAnd,
    ast.LShift: ast.RShift, ast.RShift: ast.LShift,
}
SYMBOLS: Dict[type, str] = {
    ast.Eq: "==", ast.NotEq: "!=", ast.Lt: "<", ast.LtE: "<=", ast.Gt: ">", ast.GtE: ">=",
    ast.Is: "is", ast.IsNot: "is not", ast.In: "in", ast.NotIn: "not in",
    ast.Add: "+", ast.Sub: "-", ast.Mult: "*", ast.Div: "/", ast.FloorDiv: "//",
    ast.Mod: "%", ast.Pow: "**", ast.BitAnd: "&", ast.BitOr: "|", ast.BitXor: "^",
    ast.LShift: "<<", ast.RShift: ">>", ast.And: "and", ast.Or: "or",
}


class GuardError(Exception):
    """A usage or environment problem (exit code 2)."""


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
# Target lookup and mutation operators
# --------------------------------------------------------------------------------------
FunctionNode = Any  # ast.FunctionDef or ast.AsyncFunctionDef


def parse_target(spec: str) -> Tuple[str, str]:
    """Split ``path.py:qualified.name`` into its two parts (Windows drive letters are safe)."""
    if ":" not in spec:
        raise GuardError(f"target must look like path/to/file.py:function_name, got {spec!r}")
    path, _, qualname = spec.rpartition(":")
    if not path or not qualname:
        raise GuardError(f"target must look like path/to/file.py:function_name, got {spec!r}")
    return path, qualname


def find_function(tree: ast.AST, qualname: str) -> FunctionNode:
    """Locate ``function`` or ``Class.method`` (nesting allowed) inside a parsed module."""
    scope: Any = tree
    node: Any = None
    for part in qualname.split("."):
        node = None
        for child in getattr(scope, "body", []):
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and child.name == part:
                node = child
                break
        if node is None:
            raise GuardError(f"cannot find '{qualname}' (missing '{part}')")
        scope = node
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise GuardError(f"'{qualname}' is a class, not a function or method")
    return node


@dataclass
class Mutant:
    """One rewritten version of the target file."""

    index: int
    kind: str
    line: int
    description: str
    source: str


class Mutator(ast.NodeTransformer):
    """Counts mutation sites; applies the one whose ordinal equals ``target``."""

    def __init__(self, enabled: Sequence[str], target: int = -1) -> None:
        self.enabled = set(enabled)
        self.target = target
        self.counter = 0
        self.sites: List[Tuple[str, int, str]] = []

    def _hit(self, kind: str, node: ast.AST, description: str) -> bool:
        if kind not in self.enabled:
            return False
        ordinal = self.counter
        self.counter += 1
        self.sites.append((kind, getattr(node, "lineno", 0), description))
        return ordinal == self.target

    def visit_Expr(self, node: ast.Expr) -> ast.AST:
        if isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            return node  # docstrings and bare strings: mutating them changes nothing observable
        return self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.AST:
        return node  # keep f-string layout intact

    def visit_Compare(self, node: ast.Compare) -> ast.AST:
        self.generic_visit(node)
        for position, op in enumerate(node.ops):
            swap = COMPARE_SWAPS.get(type(op))
            if swap and self._hit("compare", node, f"{SYMBOLS[type(op)]} -> {SYMBOLS[swap]}"):
                node.ops[position] = swap()
        return node

    def visit_BinOp(self, node: ast.BinOp) -> ast.AST:
        self.generic_visit(node)
        swap = ARITH_SWAPS.get(type(node.op))
        if swap and self._hit("arith", node, f"{SYMBOLS[type(node.op)]} -> {SYMBOLS[swap]}"):
            node.op = swap()
        return node

    def visit_BoolOp(self, node: ast.BoolOp) -> ast.AST:
        self.generic_visit(node)
        swapped = ast.Or if isinstance(node.op, ast.And) else ast.And
        if self._hit("bool", node, f"{SYMBOLS[type(node.op)]} -> {SYMBOLS[swapped]}"):
            node.op = swapped()
        return node

    def visit_UnaryOp(self, node: ast.UnaryOp) -> ast.AST:
        self.generic_visit(node)
        if isinstance(node.op, ast.Not) and self._hit("not", node, "remove 'not'"):
            return node.operand
        return node

    def _negate(self, node: Any, label: str) -> ast.AST:
        self.generic_visit(node)
        if self._hit("if", node, f"negate {label} condition"):
            node.test = ast.UnaryOp(op=ast.Not(), operand=node.test)
        return node

    def visit_If(self, node: ast.If) -> ast.AST:
        return self._negate(node, "if")

    def visit_IfExp(self, node: ast.IfExp) -> ast.AST:
        return self._negate(node, "conditional-expression")

    def visit_Return(self, node: ast.Return) -> ast.AST:
        self.generic_visit(node)
        value = node.value
        if value is None or (isinstance(value, ast.Constant) and value.value is None):
            return node
        if self._hit("return", node, "return None instead of the computed value"):
            node.value = ast.Constant(value=None)
        return node

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        value = node.value
        if isinstance(value, bool):
            if self._hit("const", node, f"{value} -> {not value}"):
                return ast.copy_location(ast.Constant(value=not value), node)
        elif isinstance(value, int):
            if self._hit("const", node, f"{value} -> {value + 1}"):
                return ast.copy_location(ast.Constant(value=value + 1), node)
        elif isinstance(value, str):
            replacement = "" if value else "mutated"
            if self._hit("const", node, f"{value!r} -> {replacement!r}"):
                return ast.copy_location(ast.Constant(value=replacement), node)
        return node


def _apply_to_function(func: FunctionNode, mutator: Mutator) -> None:
    func.body = [mutator.visit(stmt) for stmt in func.body]


def _neutralize(func: FunctionNode) -> None:
    """Replace the body with ``return None`` while keeping the docstring."""
    keep = []
    first = func.body[0] if func.body else None
    if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
        keep.append(first)
    func.body = keep + [ast.Return(value=ast.Constant(value=None))]


def generate_mutants(source: str, filename: str, qualname: str, kinds: Sequence[str]) -> Tuple[List[Mutant], int]:
    """Return ``(mutants, skipped_invalid)``. Index 0 is always the neutralize mutant."""
    try:
        tree = ast.parse(source, filename=filename)
    except SyntaxError as exc:
        raise GuardError(f"cannot parse {filename}: {exc}") from exc
    find_function(tree, qualname)

    probe_tree = copy.deepcopy(tree)
    counter = Mutator(kinds)
    _apply_to_function(find_function(probe_tree, qualname), counter)
    sites = counter.sites

    def render(mutated: ast.AST) -> Optional[str]:
        ast.fix_missing_locations(mutated)
        text = ast.unparse(mutated) + "\n"
        try:
            compile(text, filename, "exec")
        except (SyntaxError, ValueError):
            return None
        return text

    mutants: List[Mutant] = []
    skipped = 0
    neutral_tree = copy.deepcopy(tree)
    _neutralize(find_function(neutral_tree, qualname))
    text = render(neutral_tree)
    if text is None:
        raise GuardError("could not build the neutralized version of the target")
    mutants.append(Mutant(0, "neutralize", find_function(tree, qualname).lineno, "replace the whole body with 'return None'", text))

    for ordinal, (kind, line, description) in enumerate(sites):
        candidate = copy.deepcopy(tree)
        _apply_to_function(find_function(candidate, qualname), Mutator(kinds, target=ordinal))
        rendered = render(candidate)
        if rendered is None:
            skipped += 1
            continue
        mutants.append(Mutant(len(mutants), kind, line, description, rendered))
    return mutants, skipped


def sample_mutants(mutants: List[Mutant], limit: int) -> List[Mutant]:
    """Keep the neutralize mutant and an evenly spaced sample of the rest."""
    if limit <= 0 or len(mutants) <= limit:
        return mutants
    rest = mutants[1:]
    slots = max(limit - 1, 0)
    if slots == 0:
        return mutants[:1]
    step = len(rest) / slots
    chosen = [rest[int(i * step)] for i in range(slots)]
    return [mutants[0]] + chosen


# --------------------------------------------------------------------------------------
# Test execution
# --------------------------------------------------------------------------------------
@dataclass
class RunResult:
    status: str  # passed | failed | timeout
    returncode: Optional[int]
    seconds: float
    output: str = ""


def build_command(runner: Optional[str], test_path: str) -> List[str]:
    """Build the test command; ``{test}`` in a custom runner is replaced by the test path."""
    if not runner:
        return [sys.executable, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", "--no-header", test_path]
    tokens = shlex.split(runner, posix=os.name != "nt")
    tokens = [t[1:-1] if len(t) >= 2 and t[0] == t[-1] and t[0] in "\"'" else t for t in tokens]
    if not tokens:
        raise GuardError("--runner is empty")
    if any("{test}" in token for token in tokens):
        return [token.replace("{test}", test_path) for token in tokens]
    return tokens + [test_path]


def run_tests(command: Sequence[str], cwd: Path, timeout: int) -> RunResult:
    environment = dict(os.environ)
    # INVARIANT(NI-007): mutants keep the original file size, so stale bytecode must never be reused.
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    environment["MUTATION_GUARD"] = "1"
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command),
            cwd=str(cwd),
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return RunResult("timeout", None, time.monotonic() - started)
    except (FileNotFoundError, PermissionError) as exc:
        raise GuardError(
            f"cannot start the test runner {command[0]!r}: it was not found or is not executable. "
            "Check --runner, or install the runner."
        ) from exc
    elapsed = time.monotonic() - started
    status = "passed" if completed.returncode == 0 else "failed"
    return RunResult(status, completed.returncode, elapsed, (completed.stdout or "") + (completed.stderr or ""))


# --------------------------------------------------------------------------------------
# Safe in-place mutation of the target file
# --------------------------------------------------------------------------------------
class TargetGuard:
    """Owns the target file while it is mutated and guarantees it is put back."""

    def __init__(self, target: Path) -> None:
        self.target = target
        self.backup = target.with_name(target.name + BACKUP_SUFFIX)
        self.original = target.read_bytes()
        self._stat = target.stat()
        self._armed = False
        self._old_handlers: Dict[int, Any] = {}

    def arm(self) -> None:
        # INVARIANT(NI-006): backup -- a copy on disk survives even a hard kill of this process.
        self.backup.write_bytes(self.original)
        self._armed = True
        atexit.register(self.restore)
        # INVARIANT(NI-006): signals -- Ctrl+C and termination requests must restore the file first.
        names = ["SIGINT", "SIGTERM", "SIGBREAK", "SIGHUP"]
        for name in names:
            number = getattr(signal, name, None)
            if number is None:
                continue
            try:
                self._old_handlers[number] = signal.signal(number, self._on_signal)
            except (ValueError, OSError):
                continue

    def _on_signal(self, number: int, _frame: Any) -> None:
        self.restore()
        raise SystemExit(128 + number)

    def write_mutant(self, source: str) -> None:
        self.target.write_bytes(source.encode("utf-8"))

    def restore(self) -> None:
        """Put the original bytes back and delete the backup. Safe to call repeatedly."""
        if not self._armed:
            return
        self.target.write_bytes(self.original)
        try:
            os.utime(self.target, ns=(self._stat.st_atime_ns, self._stat.st_mtime_ns))
        except OSError:
            pass
        try:
            os.remove(self.backup)
        except OSError:
            pass
        for number, handler in self._old_handlers.items():
            try:
                signal.signal(number, handler)
            except (ValueError, OSError):
                pass
        self._old_handlers.clear()
        self._armed = False


def recover(target: Path, style: Style) -> int:
    """Restore a target file from a leftover backup after an unclean exit."""
    backup = target.with_name(target.name + BACKUP_SUFFIX)
    if not backup.is_file():
        print(style.yellow(f"[warn] no backup found for {target}; nothing to recover."))
        return 0
    target.write_bytes(backup.read_bytes())
    os.remove(backup)
    print(style.green(f"[ok] restored {target} from {backup.name}"))
    return 0


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------
@dataclass
class MutantOutcome:
    mutant: Mutant
    result: RunResult

    @property
    def killed(self) -> bool:
        return self.result.status != "passed"

    @property
    def label(self) -> str:
        if self.result.status == "timeout":
            return "KILLED (timeout)"
        return "KILLED" if self.killed else "SURVIVED"


@dataclass
class Report:
    target: str
    test: str
    baseline: Optional[RunResult]
    outcomes: List[MutantOutcome] = field(default_factory=list)
    skipped_invalid: int = 0
    min_score: float = DEFAULT_MIN_SCORE

    @property
    def killed(self) -> int:
        return sum(1 for o in self.outcomes if o.killed)

    @property
    def score(self) -> float:
        return self.killed / len(self.outcomes) if self.outcomes else 0.0

    @property
    def neutralize_killed(self) -> bool:
        return any(o.mutant.kind == "neutralize" and o.killed for o in self.outcomes)

    @property
    def passed(self) -> bool:
        return self.neutralize_killed and self.score >= self.min_score


def print_table(report: Report, style: Style) -> None:
    print(f"{'#':>3}  {'line':>5}  {'operator':<10} {'mutation':<46} result")
    for outcome in report.outcomes:
        mutant = outcome.mutant
        label = style.green(outcome.label) if outcome.killed else style.red(outcome.label)
        description = mutant.description if len(mutant.description) <= 46 else mutant.description[:43] + "..."
        print(f"{mutant.index:>3}  {mutant.line:>5}  {mutant.kind:<10} {description:<46} {label} {style.dim(f'{outcome.result.seconds:.2f}s')}")


def report_as_dict(report: Report) -> Dict[str, Any]:
    return {
        "target": report.target,
        "test": report.test,
        "passed": report.passed,
        "score": round(report.score, 4),
        "min_score": report.min_score,
        "killed": report.killed,
        "total": len(report.outcomes),
        "neutralize_killed": report.neutralize_killed,
        "skipped_invalid": report.skipped_invalid,
        "mutants": [
            {
                "index": o.mutant.index,
                "kind": o.mutant.kind,
                "line": o.mutant.line,
                "description": o.mutant.description,
                "result": o.label,
                "seconds": round(o.result.seconds, 3),
            }
            for o in report.outcomes
        ],
    }


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="mutation_guard.py",
        description="Verify that a test fails when the function it claims to protect is broken.",
        epilog=(
            "examples:\n"
            "  python scripts/mutation_guard.py --test tests/test_parse.py --target src/parse.py:parse_line\n"
            "  python scripts/mutation_guard.py --test tests/test_a.py --target src/a.py:Cache.get --min-score 0.8\n"
            "  python scripts/mutation_guard.py --test t.py --target m.py:f --runner \"python -m unittest {test}\"\n"
            "  python scripts/mutation_guard.py --target src/parse.py:parse_line --test x --list\n"
            "  python scripts/mutation_guard.py --target src/parse.py:parse_line --test x --recover\n"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--test", required=True, help="path to the test file (or directory) to run")
    parser.add_argument("--target", required=True, help="function to mutate, as path/to/file.py:function or file.py:Class.method")
    parser.add_argument("--runner", help="custom test command; {test} is replaced by the test path (default: python -m pytest -x -q)")
    parser.add_argument("--cwd", default=".", help="directory to run tests from (default: current directory)")
    parser.add_argument("--operators", default=",".join(KINDS), help=f"comma-separated mutation operators (default: all of {', '.join(KINDS)})")
    parser.add_argument("--max-mutants", type=int, default=DEFAULT_MAX_MUTANTS, metavar="N", help=f"cap on mutants to run, 0 = unlimited (default {DEFAULT_MAX_MUTANTS})")
    parser.add_argument("--min-score", type=float, default=DEFAULT_MIN_SCORE, metavar="RATIO", help=f"minimum fraction of mutants that must be killed, 0-1 (default {DEFAULT_MIN_SCORE})")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, metavar="SEC", help=f"per-run timeout; a timeout counts as killed (default {DEFAULT_TIMEOUT})")
    parser.add_argument("--skip-baseline", action="store_true", help="do not run the unmodified tests first")
    parser.add_argument("--list", action="store_true", help="list the mutants without running any tests or touching files")
    parser.add_argument("--recover", action="store_true", help="restore the target from a leftover .mgbak backup and exit")
    parser.add_argument("--format", choices=("text", "json"), default="text", help="output format (default: text)")
    parser.add_argument("--no-color", action="store_true", help="disable ANSI colors")
    parser.add_argument("--version", action="version", version=f"%(prog)s {VERSION}")
    return parser


def execute(args: argparse.Namespace, style: Style) -> int:
    cwd = Path(args.cwd).resolve()
    if not cwd.is_dir():
        raise GuardError(f"--cwd is not a directory: {cwd}")
    relative_path, qualname = parse_target(args.target)
    target = Path(relative_path)
    target = target if target.is_absolute() else cwd / target
    if args.recover:
        return recover(target, style)
    if not target.is_file():
        raise GuardError(f"target file not found: {target}")
    if target.suffix != ".py":
        raise GuardError("only Python targets (.py) can be mutated")
    test_path = Path(args.test)
    if not (test_path if test_path.is_absolute() else cwd / test_path).exists() and not args.runner:
        raise GuardError(f"test path not found: {args.test}")
    if not 0.0 <= args.min_score <= 1.0:
        raise GuardError("--min-score must be between 0 and 1")
    kinds = [k.strip() for k in args.operators.split(",") if k.strip()]
    unknown = [k for k in kinds if k not in KINDS]
    if unknown:
        raise GuardError(f"unknown operator(s): {', '.join(unknown)}; choose from {', '.join(KINDS)}")
    backup = target.with_name(target.name + BACKUP_SUFFIX)
    if backup.exists() and not args.list:
        raise GuardError(f"found a leftover backup {backup.name}: a previous run was interrupted. Inspect it, then run with --recover")

    source = target.read_text(encoding="utf-8")
    mutants, skipped = generate_mutants(source, str(target), qualname, kinds)
    selected = sample_mutants(mutants, args.max_mutants)
    quiet = args.format == "json"

    if args.list:
        print(style.bold(f"{len(mutants)} mutants for {args.target}") + (f"  ({skipped} invalid skipped)" if skipped else ""))
        for mutant in mutants:
            print(f"{mutant.index:>3}  line {mutant.line:<5} {mutant.kind:<10} {mutant.description}")
        return 0

    command = build_command(args.runner, args.test)
    if not quiet:
        print(style.bold("Mutation guard") + f"  {args.target}  <-  {args.test}")
        print(style.dim(f"runner: {' '.join(command)}"))
    report = Report(args.target, args.test, None, skipped_invalid=skipped, min_score=args.min_score)

    if not args.skip_baseline:
        baseline = run_tests(command, cwd, args.timeout)
        report.baseline = baseline
        if baseline.status != "passed":
            tail = "\n".join(baseline.output.strip().splitlines()[-25:])
            print(style.red(f"[FAIL] baseline run {baseline.status}: the tests must pass before they can be mutation-verified."), file=sys.stderr)
            if tail:
                print(tail, file=sys.stderr)
            return 2
        if not quiet:
            print(style.green(f"[ok] baseline passed") + style.dim(f" ({baseline.seconds:.2f}s)"))

    guard = TargetGuard(target)
    guard.arm()
    try:
        for mutant in selected:
            guard.write_mutant(mutant.source)
            result = run_tests(command, cwd, args.timeout)
            report.outcomes.append(MutantOutcome(mutant, result))
    finally:
        # INVARIANT(NI-006): restore -- runs on success, on errors, and on Ctrl+C.
        guard.restore()

    if quiet:
        print(json.dumps(report_as_dict(report), indent=2))
        return 0 if report.passed else 1

    print()
    print_table(report, style)
    print()
    total = len(report.outcomes)
    print(f"Killed {report.killed}/{total} mutants ({report.score:.0%}); required at least {report.min_score:.0%}.")
    if len(selected) < len(mutants):
        print(style.dim(f"Sampled {len(selected)} of {len(mutants)} mutants; raise --max-mutants for full coverage."))
    if skipped:
        print(style.dim(f"{skipped} mutant(s) were skipped because they did not compile."))
    survivors = [o for o in report.outcomes if not o.killed and o.mutant.kind != "neutralize"]
    if not report.neutralize_killed:
        print(style.red("[FAIL] The tests still pass when the function does nothing."))
        print("       They do not exercise this function, or they mock away its behavior. Write a test that asserts on its real output.")
    elif report.score < report.min_score:
        print(style.red("[FAIL] Too many mutants survived; the assertions are too weak."))
    else:
        print(style.green("[ok] The tests fail when the function is broken."))
    for outcome in survivors[:10]:
        print(style.yellow(f"       survivor: line {outcome.mutant.line}: {outcome.mutant.description}"))
    return 0 if report.passed else 1


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    style = Style(supports_color(sys.stdout) and not args.no_color)
    try:
        return execute(args, style)
    except GuardError as exc:
        print(style.red(f"error: {exc}"), file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        print(style.yellow("\ninterrupted; the target file was restored."), file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
