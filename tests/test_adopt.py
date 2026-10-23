"""Tests for scripts/adopt.py: installing the framework into another project.

The key property is that an adopted project passes its own guardrails on day one. Before v1.5.0 the
quickstart copied this repository's invariants, whose NI-010 rule requires a Claude Code hook file that
adopters never receive, so the invariant check failed in every adopted project.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


adopt = load("adopt", ROOT / "scripts" / "adopt.py")


def make_project(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    (project / "app").mkdir(parents=True)
    # Application code may spawn processes: the tooling rules must not reach it.
    (project / "app" / "core.py").write_text("import subprocess\n\ndef run():\n    return 1\n", encoding="utf-8")
    return project


def run_adopt(project: Path, *extra: str) -> int:
    return adopt.main(["--target", str(project), "--no-color", *extra])


def test_adopted_project_passes_its_own_invariant_check(tmp_path: Path, capsys) -> None:
    project = make_project(tmp_path)
    assert run_adopt(project, "--agent", "claude") == 0
    verifier = load("verify_invariants_adopted", project / "scripts" / "verify_invariants.py")
    capsys.readouterr()
    status = verifier.main(["--root", str(project), "--no-color", "--require-rules"])
    assert status == 0, capsys.readouterr().out


def test_adopted_map_covers_every_path(tmp_path: Path, capsys) -> None:
    project = make_project(tmp_path)
    assert run_adopt(project, "--agent", "claude", "--agent", "cursor", "--ci") == 0
    init_mapping = load("init_mapping_adopted", project / "scripts" / "init_mapping.py")
    assert init_mapping.main(["--root", str(project), "--check", "--no-color"]) == 0
    assert "app/core.py" in (project / "maps" / "project-map.md").read_text(encoding="utf-8")


def test_claude_md_is_a_byte_identical_copy_of_the_stack_manifesto(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert run_adopt(project, "--stack", "typescript", "--agent", "claude") == 0
    template = (ROOT / "templates" / "typescript" / "AGENTS.md").read_bytes()
    assert (project / "AGENTS.md").read_bytes() == template
    assert (project / "CLAUDE.md").read_bytes() == template
    assert (project / "tests" / "test_maps.test.ts").is_file()
    assert not (project / "tests" / "test_maps.py").exists()


def test_existing_files_are_never_overwritten(tmp_path: Path, capsys) -> None:
    project = make_project(tmp_path)
    (project / "AGENTS.md").write_text("my own rules\n", encoding="utf-8")
    (project / "maps").mkdir()
    (project / "maps" / "project-map.md").write_text("my own map\n", encoding="utf-8")
    assert run_adopt(project) == 0
    out = capsys.readouterr().out
    assert (project / "AGENTS.md").read_text(encoding="utf-8") == "my own rules\n"
    assert (project / "maps" / "project-map.md").read_text(encoding="utf-8") == "my own map\n"
    assert "skip  AGENTS.md" in out
    assert "skip  maps/project-map.md" in out
    assert (project / "scripts" / "verify_invariants.py").is_file()
    copied = len(adopt.COMMON_FILES) + len(adopt.STACK_FILES["python"]) - 1  # minus the existing AGENTS.md
    assert f"Added {copied} file(s), skipped 1." in out
    assert "1. Refresh the map: python scripts/init_mapping.py --merge" in out


def test_a_second_run_changes_nothing(tmp_path: Path, capsys) -> None:
    project = make_project(tmp_path)
    assert run_adopt(project, "--agent", "claude") == 0
    snapshot = {p: p.read_bytes() for p in project.rglob("*") if p.is_file()}
    capsys.readouterr()
    assert run_adopt(project, "--agent", "claude") == 0
    assert {p: p.read_bytes() for p in project.rglob("*") if p.is_file()} == snapshot
    assert "Added 0 file(s)" in capsys.readouterr().out


def test_a_failed_map_generation_is_reported(tmp_path: Path, monkeypatch, capsys) -> None:
    project = make_project(tmp_path)
    monkeypatch.setattr(adopt, "load_init_mapping", lambda framework: (lambda argv: 3))
    assert run_adopt(project) == 3
    captured = capsys.readouterr()
    assert "init_mapping.py exited 3" in captured.err
    assert "Next steps" not in captured.out


def test_dry_run_writes_nothing(tmp_path: Path, capsys) -> None:
    project = make_project(tmp_path)
    before = sorted(p.relative_to(project).as_posix() for p in project.rglob("*"))
    assert run_adopt(project, "--agent", "claude", "--ci", "--dry-run") == 0
    after = sorted(p.relative_to(project).as_posix() for p in project.rglob("*"))
    assert after == before
    out = capsys.readouterr().out
    assert "add   .github/workflows/ai-guardrails.yml" in out
    assert out.startswith("Plan for ")
    assert "Would add " in out


def test_agent_entry_files(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert run_adopt(project, "--stack", "generic", "--agent", "codex", "--agent", "copilot") == 0
    assert (project / ".github" / "copilot-instructions.md").is_file()
    assert not (project / "CLAUDE.md").exists()  # codex reads AGENTS.md, so nothing else is written
    assert not (project / ".cursor").exists()
    assert not (project / "tests").exists()  # the generic stack has no map test


def test_next_steps_follow_the_stack_and_the_agents() -> None:
    python_claude = adopt.next_steps("python", ["claude"], wrote_map=True)
    assert python_claude == [
        "Describe every row in maps/project-map.md that ends with 'describe manually'.",
        "Review invariants/negative-invariants.md: keep the rules that fit, then add your own.",
        "Run the map test: python -m pytest -q tests/test_maps.py",
        "Check the rules: python scripts/verify_invariants.py",
        "Run the checks on every commit: sh scripts/install_hooks.sh",
        "Claude Code: install the plugin for hooks, skills, and the MCP server (see the README).",
    ]
    typescript_codex = adopt.next_steps("typescript", ["codex"], wrote_map=True)
    assert "Run the map test with your runner, for example: npx vitest run tests/test_maps.test.ts" in typescript_codex
    assert typescript_codex[-1] == "Cursor and Codex: connect the MCP server with the config in mcp/README.md."
    assert adopt.next_steps("generic", ["cursor"], wrote_map=True)[-1].startswith("Cursor and Codex")
    generic = adopt.next_steps("generic", [], wrote_map=True)
    assert not any("map test" in line or "Claude Code" in line or "Cursor" in line for line in generic)


def test_ci_workflow_is_only_written_on_request(tmp_path: Path) -> None:
    project = make_project(tmp_path)
    assert run_adopt(project) == 0
    assert not (project / ".github" / "workflows" / "ai-guardrails.yml").exists()


@pytest.mark.parametrize("argv", [["--stack", "rust"], ["--agent", "gemini"]])
def test_unknown_choices_are_usage_errors(tmp_path: Path, argv) -> None:
    with pytest.raises(SystemExit) as exc:
        run_adopt(make_project(tmp_path), *argv)
    assert exc.value.code == 2


def test_missing_target_and_the_framework_itself_are_refused(tmp_path: Path, capsys) -> None:
    assert run_adopt(tmp_path / "does-not-exist") == 2
    assert adopt.main(["--target", str(ROOT), "--no-color"]) == 2
    assert "framework repository itself" in capsys.readouterr().err


def rule_blocks(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    blocks = re.findall(r"```invariant-rule\n(.*?)```", text, re.S)
    return {rule["id"]: rule for rule in map(json.loads, blocks)}


def test_adopter_invariants_stay_in_sync_with_the_framework() -> None:
    ours = rule_blocks(ROOT / "invariants" / "negative-invariants.md")
    theirs = rule_blocks(ROOT / "templates" / "invariants" / "negative-invariants.md")
    # NI-010 guards a hook file that adopters do not receive.
    assert set(theirs) == set(ours) - {"NI-010"}
    for rule_id in theirs:
        if rule_id == "NI-002":
            continue
        assert theirs[rule_id] == ours[rule_id], rule_id
    # NI-002 keeps its contract but covers only the tooling, never the adopter's own code.
    for key in ("type", "modules", "allowed_in", "use"):
        assert theirs["NI-002"][key] == ours["NI-002"][key]
    assert theirs["NI-002"]["scope"] == ours["NI-001"]["scope"]
