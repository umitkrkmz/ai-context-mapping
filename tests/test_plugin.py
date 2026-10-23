"""Tests for the Claude Code plugin: the repository root is both the marketplace and the plugin.

These are static checks of the manifests, hooks, and skills. `claude plugin validate .` remains the
authoritative check of the formats; it is part of the release checklist, not of this suite, because
it needs the Claude Code CLI.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PLUGIN = json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
MARKETPLACE = json.loads((ROOT / ".claude-plugin" / "marketplace.json").read_text(encoding="utf-8"))
HOOKS = json.loads((ROOT / "hooks" / "hooks.json").read_text(encoding="utf-8"))
SKILLS = sorted((ROOT / "skills").glob("*/SKILL.md"))
PLUGIN_PATH = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([\w./-]+\.py)")


def hook_commands() -> list:
    return [h["command"] for groups in HOOKS["hooks"].values() for group in groups for h in group["hooks"]]


def test_marketplace_lists_the_repository_root_as_the_plugin() -> None:
    assert MARKETPLACE["owner"]["name"]
    entries = MARKETPLACE["plugins"]
    assert [e["name"] for e in entries] == [PLUGIN["name"]] == ["ai-context-mapping"]
    assert entries[0]["source"] == "."
    assert MARKETPLACE["name"] == "ai-context-mapping"


def test_the_map_gate_is_opt_in_and_off_by_default() -> None:
    option = PLUGIN["userConfig"]["map_gate"]
    assert option["type"] == "boolean" and option["default"] is False
    gate = [c for c in hook_commands() if "map_gate.py" in c]
    assert len(gate) == 1
    # The option is read first: anything but an explicit true exits 0 before the gate script runs.
    command = gate[0]
    assert command.startswith('case "${CLAUDE_PLUGIN_OPTION_MAP_GATE:-}" in true|True|TRUE|1) ;; *) exit 0 ;; esac;')
    assert command.index("esac;") < command.index("map_gate.py")


def test_plugin_gate_covers_the_same_tools_as_the_repositorys_own_gate() -> None:
    settings = json.loads((ROOT / ".claude" / "settings.json").read_text(encoding="utf-8"))

    def gate_matcher(groups) -> str:
        return next(g["matcher"] for g in groups if "map_gate.py" in json.dumps(g))

    assert gate_matcher(HOOKS["hooks"]["PreToolUse"]) == gate_matcher(settings["hooks"]["PreToolUse"])


def test_every_bundled_path_exists() -> None:
    referenced = set()
    for text in [*hook_commands(), *PLUGIN["mcpServers"]["ai-context-mapping"]["args"]]:
        referenced.update(PLUGIN_PATH.findall(text))
    for skill in SKILLS:
        referenced.update(PLUGIN_PATH.findall(skill.read_text(encoding="utf-8")))
    assert {".claude/hooks/guardrail_hook.py", ".claude/hooks/map_gate.py", "mcp/context_server.py",
            "scripts/adopt.py"} <= referenced
    for path in referenced:
        assert (ROOT / path).is_file(), path


def test_every_user_config_option_is_used() -> None:
    hooks_text = json.dumps(HOOKS)
    mcp_text = json.dumps(PLUGIN["mcpServers"])
    for key in PLUGIN["userConfig"]:
        assert f"CLAUDE_PLUGIN_OPTION_{key.upper()}" in hooks_text or f"${{user_config.{key}}}" in mcp_text, key


def test_the_mcp_server_serves_the_users_project_not_the_plugin() -> None:
    args = PLUGIN["mcpServers"]["ai-context-mapping"]["args"]
    assert args[args.index("--root") + 1] == "${CLAUDE_PROJECT_DIR}"


def test_skills_have_frontmatter_and_the_installer_is_user_only() -> None:
    names = {skill.parent.name for skill in SKILLS}
    assert names == {"adopt", "verify-map", "verify-invariants", "mutation-test", "diet-check"}
    for skill in SKILLS:
        text = skill.read_text(encoding="utf-8")
        assert text.startswith("---\n"), skill
        front = text.split("---\n", 2)[1]
        assert re.search(r"^description: \S", front, re.M), skill
    adopt_front = (ROOT / "skills" / "adopt" / "SKILL.md").read_text(encoding="utf-8").split("---\n", 2)[1]
    assert "disable-model-invocation: true" in adopt_front  # it writes files; only the user starts it


def test_no_stray_plugin_components_at_the_repository_root() -> None:
    # Claude Code loads these default locations from a plugin root. Adding one here by accident would
    # ship it to every plugin user.
    for name in ("commands", "agents", "bin", "output-styles", "monitors", "workflows", "themes",
                 ".mcp.json", ".lsp.json", "settings.json"):
        assert not (ROOT / name).exists(), name
