"""Tests for the Claude Code hooks in .claude/hooks/ and their wiring in .claude/settings.json.

map_gate.py enforces Rule 1 (read the project map before searching). These tests feed it mock
PreToolUse payloads and check the exit codes Claude Code acts on: 0 allows the call, 2 blocks it.
guardrail_hook.py gets a few checks for its git-commit detection.

The hooks are not a package, so they are loaded by path. Standard library plus pytest only.
"""
from __future__ import annotations

import importlib.util
import io
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOKS = ROOT / ".claude" / "hooks"


def load_hook(name: str):
    spec = importlib.util.spec_from_file_location(name, HOOKS / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


gate_module = load_hook("map_gate")
guard_module = load_hook("guardrail_hook")


@pytest.fixture()
def project(tmp_path: Path) -> Path:
    """A throwaway project that has a map."""
    (tmp_path / "maps").mkdir()
    (tmp_path / "maps" / "project-map.md").write_text("# Project Map\n", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
    return tmp_path


def env_for(project: Path, **extra: str) -> Dict[str, str]:
    env = {"CLAUDE_PROJECT_DIR": str(project), "AI_GUARDRAILS_STATE_DIR": str(project / ".state")}
    env.update(extra)
    return env


def payload(tool: str, session: str = "s1", agent: Optional[str] = None, **tool_input: Any) -> Dict[str, Any]:
    data: Dict[str, Any] = {"session_id": session, "tool_name": tool, "tool_input": tool_input}
    if agent:
        data["agent_id"] = agent
    return data


def run(project: Path, data: Dict[str, Any], **extra_env: str):
    return gate_module.gate(data, env_for(project, **extra_env))


def bash(command: str, **kw: Any) -> Dict[str, Any]:
    return payload("Bash", command=command, **kw)


# --------------------------------------------------------------------------------------
# Blocking: search tools and exploratory commands before the map is read
# --------------------------------------------------------------------------------------
def test_grep_tool_is_blocked_before_the_map_is_read(project: Path) -> None:
    code, message = run(project, payload("Grep", pattern="free_shipping"))
    assert code == 2
    assert message.startswith("Rule 1 Enforced: Access denied.")
    assert "maps/project-map.md" in message and "MCP context server" in message


def test_glob_tool_is_blocked_before_the_map_is_read(project: Path) -> None:
    assert run(project, payload("Glob", pattern="**/*"))[0] == 2


@pytest.mark.parametrize(
    "command",
    [
        "grep -rn free_shipping .",
        "grep -R TODO src",
        "grep needle src/app.py",
        "grep -e needle src/app.py",
        "egrep -r foo .",
        "rg free_shipping",
        "rg -n foo src/",
        "ag needle src",
        "ack needle",
        "find . -name '*.py'",
        "fd shipping",
        "tree src",
        "ls -R",
        "ls -lR src",
        "git grep foo",
        "git -C sub grep foo",
        "git status && grep -r x .",
        "cd src; find .",
        "FOO=1 grep -r x .",
        "sudo grep -r x /etc",
    ],
)
def test_exploratory_shell_commands_are_blocked(project: Path, command: str) -> None:
    assert run(project, bash(command))[0] == 2, command


@pytest.mark.parametrize(
    "command",
    ["Select-String -Path src -Pattern foo", "Get-ChildItem -Recurse", "gci . -r", "sls foo *.py"],
)
def test_powershell_search_is_blocked(project: Path, command: str) -> None:
    assert run(project, payload("PowerShell", command=command))[0] == 2, command


# --------------------------------------------------------------------------------------
# Never blocking: everything that is not a search
# --------------------------------------------------------------------------------------
@pytest.mark.parametrize(
    "command",
    [
        "git status",
        "git commit -m 'fix: find bug; grep it later'",
        "python -m pytest -q",
        "python -m pytest -q | grep passed",
        "python -m pytest 2>&1 | grep -E 'FAIL|passed' | tail -3",
        "cat README.md | grep -i license",
        "cat README.md",
        "ls",
        "ls -la src",
        "echo 'find this' > note.txt",
        "python scripts/verify_invariants.py",
        "sh scripts/install_hooks.sh",
        "sed -n 1,20p src/app.py",
        "grep",
        "",
    ],
)
def test_non_search_commands_are_never_blocked(project: Path, command: str) -> None:
    assert run(project, bash(command)) == (0, ""), command


@pytest.mark.parametrize("tool", ["Write", "Edit", "MultiEdit", "NotebookEdit", "WebFetch", "Task", "Agent", "TodoWrite"])
def test_non_search_tools_are_never_blocked(project: Path, tool: str) -> None:
    assert run(project, payload(tool, file_path=str(project / "src" / "app.py"))) == (0, "")


def test_reading_an_ordinary_file_is_allowed_but_does_not_unlock(project: Path) -> None:
    assert run(project, payload("Read", file_path=str(project / "src" / "app.py"))) == (0, "")
    assert run(project, payload("Grep", pattern="x"))[0] == 2


# --------------------------------------------------------------------------------------
# Unlocking: any way of inspecting the map
# --------------------------------------------------------------------------------------
def test_reading_the_map_unlocks_searching(project: Path) -> None:
    assert run(project, payload("Grep", pattern="x"))[0] == 2
    assert run(project, payload("Read", file_path=str(project / "maps" / "project-map.md"))) == (0, "")
    assert run(project, payload("Grep", pattern="x")) == (0, "")
    assert run(project, payload("Glob", pattern="**/*")) == (0, "")
    assert run(project, bash("grep -rn foo .")) == (0, "")


def test_relative_and_backslash_paths_unlock(project: Path) -> None:
    assert run(project, payload("Read", file_path="maps/project-map.md")) == (0, "")
    assert run(project, payload("Grep", pattern="x")) == (0, "")


@pytest.mark.skipif(os.name != "nt", reason="drive-letter and case-insensitive paths are a Windows matter")
def test_windows_style_paths_unlock(project: Path) -> None:
    windows_path = str(project / "maps" / "project-map.md").replace("/", "\\").upper()
    assert run(project, payload("Read", file_path=windows_path)) == (0, "")
    assert run(project, payload("Grep", pattern="x")) == (0, "")


@pytest.mark.parametrize(
    "command",
    [
        "cat maps/project-map.md",
        "head -50 maps/project-map.md",
        "sed -n 1,40p maps/project-map.md",
        "grep -n shipping maps/project-map.md",
        "python mcp/context_server.py --call read_project_map",
        "python3 mcp/context_server.py --call get_file_purpose --arg file_path=src/app.py",
        "cat maps/project-map.md && grep -r foo .",
    ],
)
def test_shell_commands_that_inspect_the_map_unlock(project: Path, command: str) -> None:
    assert run(project, bash(command)) == (0, ""), command
    assert run(project, payload("Grep", pattern="x")) == (0, "")


def test_grep_tool_aimed_at_the_map_file_unlocks(project: Path) -> None:
    assert run(project, payload("Grep", pattern="shipping", path=str(project / "maps" / "project-map.md"))) == (0, "")
    assert run(project, payload("Glob", pattern="**/*.py")) == (0, "")


@pytest.mark.parametrize("tool", ["mcp__context__read_project_map", "mcp__project-context__get_file_purpose"])
def test_mcp_map_tools_unlock(project: Path, tool: str) -> None:
    assert run(project, payload(tool)) == (0, "")
    assert run(project, payload("Grep", pattern="x")) == (0, "")


def test_other_mcp_tools_do_not_unlock(project: Path) -> None:
    assert run(project, payload("mcp__github__search_code", query="x")) == (0, "")
    assert run(project, payload("Grep", pattern="x"))[0] == 2


# --------------------------------------------------------------------------------------
# Scope, bypass, and fail-open behavior
# --------------------------------------------------------------------------------------
def test_sessions_are_isolated(project: Path) -> None:
    run(project, payload("Read", session="s1", file_path="maps/project-map.md"))
    assert run(project, payload("Grep", session="s1", pattern="x"))[0] == 0
    assert run(project, payload("Grep", session="s2", pattern="x"))[0] == 2


def test_sub_agents_have_their_own_scope(project: Path) -> None:
    run(project, payload("Read", file_path="maps/project-map.md"))
    assert run(project, payload("Grep", pattern="x"))[0] == 0
    assert run(project, payload("Grep", agent="sub-1", pattern="x"))[0] == 2
    run(project, payload("Read", agent="sub-1", file_path="maps/project-map.md"))
    assert run(project, payload("Grep", agent="sub-1", pattern="x"))[0] == 0
    assert run(project, payload("Grep", agent="sub-2", pattern="x"))[0] == 2


def test_permissive_mode_disables_the_gate(project: Path) -> None:
    assert run(project, payload("Grep", pattern="x"), AI_GUARDRAILS_PERMISSIVE="1") == (0, "")
    assert run(project, bash("grep -r x ."), AI_GUARDRAILS_PERMISSIVE="1") == (0, "")
    assert run(project, payload("Grep", pattern="x"), AI_GUARDRAILS_PERMISSIVE="0")[0] == 2


def test_gate_fails_open_without_a_map(tmp_path: Path) -> None:
    assert gate_module.gate(payload("Grep", pattern="x"), env_for(tmp_path)) == (0, "")


@pytest.mark.parametrize("bad", [{}, {"tool_name": None}, {"tool_name": "Grep", "tool_input": "oops"}, {"tool_input": {}}])
def test_gate_tolerates_malformed_payloads(project: Path, bad: Dict[str, Any]) -> None:
    code, _ = run(project, bad)
    assert code in (0, 2)  # never raises; a bare Grep with a bad input shape still counts as a search


def test_unwritable_state_directory_does_not_break_the_gate(project: Path) -> None:
    blocker = project / "not-a-dir"
    blocker.write_text("file", encoding="utf-8")
    env = {"CLAUDE_PROJECT_DIR": str(project), "AI_GUARDRAILS_STATE_DIR": str(blocker / "sub")}
    assert gate_module.gate(payload("Read", file_path="maps/project-map.md"), env) == (0, "")


def test_stale_markers_are_pruned(project: Path) -> None:
    state = project / ".state"
    state.mkdir()
    stale = state / "map-read-stale.json"
    stale.write_text("{}", encoding="utf-8")
    old = 1_000_000_000
    os.utime(stale, (old, old))
    run(project, payload("Read", file_path="maps/project-map.md"))
    assert not stale.exists()


# --------------------------------------------------------------------------------------
# End to end through main(): stdin JSON in, exit code and stderr out
# --------------------------------------------------------------------------------------
def call_main(project: Path, data: Any, monkeypatch: pytest.MonkeyPatch):
    for key, value in env_for(project).items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("AI_GUARDRAILS_PERMISSIVE", raising=False)
    stderr = io.StringIO()
    text = data if isinstance(data, str) else json.dumps(data)
    code = gate_module.main([], stdin=io.StringIO(text), stderr=stderr)
    return code, stderr.getvalue()


def test_main_blocks_with_exit_code_two_and_a_message(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    code, err = call_main(project, payload("Grep", pattern="x"), monkeypatch)
    assert code == 2
    assert "Rule 1 Enforced" in err


def test_main_full_sequence(project: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert call_main(project, payload("Grep", pattern="x"), monkeypatch)[0] == 2
    assert call_main(project, payload("Read", file_path="maps/project-map.md"), monkeypatch)[0] == 0
    assert call_main(project, payload("Grep", pattern="x"), monkeypatch) == (0, "")
    assert call_main(project, bash("git status"), monkeypatch) == (0, "")


@pytest.mark.parametrize("text", ["", "not json", "[]", "null"])
def test_main_fails_open_on_garbage_input(project: Path, monkeypatch: pytest.MonkeyPatch, text: str) -> None:
    assert call_main(project, text, monkeypatch) == (0, "")


def test_status_and_reset(project: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture) -> None:
    for key, value in env_for(project).items():
        monkeypatch.setenv(key, value)
    call_main(project, payload("Read", file_path="maps/project-map.md"), monkeypatch)
    assert gate_module.main(["--status"]) == 0
    assert "markers: 1" in capsys.readouterr().out
    assert gate_module.main(["--reset"]) == 0
    assert "removed 1" in capsys.readouterr().out
    assert call_main(project, payload("Grep", pattern="x"), monkeypatch)[0] == 2


# --------------------------------------------------------------------------------------
# Shell parsing helpers
# --------------------------------------------------------------------------------------
def test_split_segments_respects_quotes_and_pipes() -> None:
    assert gate_module.split_segments("a && b | c; d") == [("a", False), ("b", False), ("c", True), ("d", False)]
    assert gate_module.split_segments("echo 'a; b | c' && d") == [("echo 'a; b | c'", False), ("d", False)]
    assert gate_module.split_segments("x || y")[1] == ("y", False)


def test_grep_operand_parsing() -> None:
    parse = gate_module.parse_operands
    assert parse(["-rn", "foo", "."]) == (["foo", "."], True, False)
    assert parse(["-e", "foo", "a.py"]) == (["a.py"], False, True)
    assert parse(["-A", "3", "foo", "a.py"]) == (["foo", "a.py"], False, False)
    assert parse(["--include=*.py", "-r", "foo"]) == (["foo"], True, False)


# --------------------------------------------------------------------------------------
# Wiring: the gate is actually configured, and the other hook's helpers behave
# --------------------------------------------------------------------------------------
def test_settings_wire_the_map_gate_for_every_search_route() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))
    entries = [e for e in settings["hooks"]["PreToolUse"] if "map_gate.py" in json.dumps(e)]
    assert entries, "no PreToolUse entry runs map_gate.py"
    matcher = entries[0]["matcher"]
    import re

    for tool in ("Grep", "Glob", "Read", "Bash", "PowerShell", "mcp__ctx__read_project_map", "mcp__ctx__get_file_purpose"):
        assert re.search(matcher, tool), f"matcher {matcher!r} does not cover {tool}"
    for tool in ("Write", "Edit"):
        assert not re.search(matcher, tool), f"matcher {matcher!r} should not cover {tool}"
    assert entries[0]["hooks"][0]["type"] == "command"


def test_the_gate_keeps_its_bypass_and_fail_open_markers() -> None:
    text = (HOOKS / "map_gate.py").read_text(encoding="utf-8")
    assert "AI_GUARDRAILS_PERMISSIVE" in text and "INVARIANT(NI-010)" in text


@pytest.mark.parametrize(
    "command, expected",
    [
        ("git commit -m x", True),
        ("git add . && git commit -am 'y'", True),
        ("git -C sub commit -m z", True),
        ("git commit-tree abc", False),
        ("git log --grep commit", False),
        ("echo hi", False),
    ],
)
def test_guardrail_hook_detects_git_commits(command: str, expected: bool) -> None:
    assert guard_module.is_git_commit({"tool_name": "Bash", "tool_input": {"command": command}}) is expected
    assert guard_module.is_git_commit({"tool_name": "Read", "tool_input": {"command": command}}) is False


# --------------------------------------------------------------------------------------
# Opt-in: a nested project's own map counts (monorepos, benchmark harnesses)
# --------------------------------------------------------------------------------------
@pytest.fixture()
def nested_map(tmp_path: Path) -> Path:
    """A second project, with its own map, that lives outside the project whose hooks are running."""
    other = tmp_path.parent / (tmp_path.name + "-other")
    (other / "maps").mkdir(parents=True)
    (other / "maps" / "project-map.md").write_text("# Other map\n", encoding="utf-8")
    (other / "docs").mkdir()
    (other / "docs" / "project-map.md").write_text("not a map\n", encoding="utf-8")
    return other


def test_a_foreign_map_does_not_unlock_by_default(project: Path, nested_map: Path) -> None:
    assert run(project, payload("Read", file_path=str(nested_map / "maps" / "project-map.md"))) == (0, "")
    assert run(project, payload("Grep", pattern="x"))[0] == 2


def test_any_map_mode_accepts_a_nested_projects_map(project: Path, nested_map: Path) -> None:
    extra = {"AI_GUARDRAILS_ANY_MAP": "1"}
    assert run(project, payload("Grep", pattern="x"), **extra)[0] == 2
    assert run(project, payload("Read", file_path=str(nested_map / "maps" / "project-map.md")), **extra) == (0, "")
    assert run(project, payload("Grep", pattern="x"), **extra) == (0, "")
    assert run(project, bash("grep -rn foo ."), **extra) == (0, "")


def test_any_map_mode_via_shell_reader(project: Path, nested_map: Path) -> None:
    extra = {"AI_GUARDRAILS_ANY_MAP": "1"}
    assert run(project, bash(f"cat {(nested_map / 'maps' / 'project-map.md').as_posix()}"), **extra) == (0, "")
    assert run(project, payload("Glob", pattern="**/*"), **extra) == (0, "")


def test_any_map_mode_rejects_lookalikes(project: Path, nested_map: Path) -> None:
    extra = {"AI_GUARDRAILS_ANY_MAP": "1"}
    assert run(project, payload("Read", file_path=str(nested_map / "docs" / "project-map.md")), **extra) == (0, "")
    assert run(project, payload("Read", file_path=str(nested_map / "maps" / "missing-map.md")), **extra) == (0, "")
    assert run(project, payload("Read", file_path=str(nested_map / "maps" / "nope" / "project-map.md")), **extra) == (0, "")
    assert run(project, payload("Grep", pattern="x"), **extra)[0] == 2


def test_is_map_file_edge_cases(project: Path, nested_map: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    is_map_file = gate_module.is_map_file
    # An empty path is a plain False (not merely falsy).
    assert is_map_file("", project) is False
    # A directory whose name merely ends in "maps" must not count as a maps/ directory.
    lookalike = nested_map.parent / "notmaps"
    lookalike.mkdir()
    (lookalike / "project-map.md").write_text("not a map\n", encoding="utf-8")
    assert is_map_file(str(lookalike / "project-map.md"), project, any_map=True) is False
    assert is_map_file(str(nested_map / "maps" / "project-map.md"), project, any_map=True) is True
    assert is_map_file(str(nested_map / "maps" / "project-map.md"), project, any_map=False) is False
    # If the path cannot be resolved, the answer is False rather than an error.
    def boom(_path):
        raise OSError("unresolvable")

    monkeypatch.setattr(gate_module.os.path, "realpath", boom)
    assert is_map_file("maps/project-map.md", project) is False
