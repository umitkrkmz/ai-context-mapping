"""Tests for the read-only MCP tools get_invariants_for_file and check_map.

The server may not import scripts/ (invariant NI-003), so it repeats two small pieces of logic: the
.agentignore matcher from init_mapping.py and the scope globs from verify_invariants.py. The parity
tests below fail as soon as either copy drifts from the script it mirrors.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


server = load("context_server", ROOT / "mcp" / "context_server.py")
init_mapping = load("init_mapping", ROOT / "scripts" / "init_mapping.py")
verify = load("verify_invariants", ROOT / "scripts" / "verify_invariants.py")

MAP_HEADER = "# Map\n\n## File Index\n\n| Path | Category | Purpose | Invariants |\n| ---- | -------- | ------- | ---------- |\n"


def write(root: Path, rel: str, text: str = "") -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def map_rows(*rows: str) -> str:
    return MAP_HEADER + "".join(f"| `{path}` | source | {purpose} | {inv} |\n" for path, purpose, inv in rows)


def script_diff(root: Path):
    """What init_mapping.py --check reports, as sets."""
    matcher = init_mapping.IgnoreMatcher.from_root(root)
    output = root / init_mapping.MAP_RELATIVE_PATH
    entries = init_mapping.ensure_map_entries(init_mapping.scan_tree(root, matcher), root, output, matcher)
    existing = init_mapping.parse_file_index(output.read_text(encoding="utf-8"))
    missing, stale = init_mapping.diff_against_map(entries, existing)
    return set(missing), set(stale)


def server_diff(root: Path):
    paths = server.scan_paths(root)
    if server.MAP_RELATIVE_PATH not in paths:
        paths.append(server.MAP_RELATIVE_PATH)
    rows = server.parse_file_index((root / server.MAP_RELATIVE_PATH).read_text(encoding="utf-8"))
    missing, stale = server.map_diff(paths, rows)
    return set(missing), set(stale)


def tricky_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    for rel in ("src/app.py", "src/gen/a.py", "src/gen/keep.py", "build/out.txt", "docs/x.md", "docs/y.md",
                "logs/run.log", "notes.txt", "data/file1.csv", "data/file2.csv", "vendor/lib/z.js", "ROADMAP.md"):
        write(root, rel)
    write(root, ".agentignore", "build/\n/logs\n*.log\nsrc/gen/*\n!src/gen/keep.py\ndata/file[12].csv\n")
    write(root, ".git/info/exclude", "ROADMAP.md\n")
    write(root, "maps/project-map.md", map_rows(
        ("src/", "Source.", "-"), ("src/app.py", "TODO describe", "-"), ("docs/**", "Docs.", "-"),
        ("gone.py", "Deleted file.", "-"), ("maps/", "Maps.", "-"), ("maps/project-map.md", "This map.", "-"),
    ))
    return root


def test_check_map_matches_init_mapping_on_tricky_ignore_rules(tmp_path: Path) -> None:
    root = tricky_project(tmp_path)
    expected = script_diff(root)
    assert server_diff(root) == expected
    missing, stale = expected
    # Sanity: the fixture exercises negation, anchoring, dir-only rules, classes, groups, and git exclude.
    assert "src/gen/keep.py" in missing and "src/gen/a.py" not in missing
    assert "notes.txt" in missing and "vendor/lib/z.js" in missing
    assert not any(p.startswith(("build", "logs", "docs/", "data/file")) for p in missing)
    assert "ROADMAP.md" not in missing
    assert stale == {"gone.py"}


def test_check_map_matches_init_mapping_on_this_repository() -> None:
    assert server_diff(ROOT) == script_diff(ROOT)


def test_check_map_reports_each_problem_kind(tmp_path: Path) -> None:
    text = server.ContextTools(tricky_project(tmp_path)).check_map({})
    assert "No row (add it):\n  - " in text and "  - notes.txt" in text
    assert "Stale row (the path is gone):\n  - gone.py" in text
    assert "Placeholder description (describe it):\n  - src/app.py" in text
    assert "--merge" in text and "Describe each placeholder row" in text


def test_check_map_on_a_current_map(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    write(root, "app.py")
    write(root, "maps/project-map.md", map_rows(("app.py", "App.", "-"), ("maps/", "Maps.", "-"),
                                                ("maps/project-map.md", "Map.", "-")))
    assert server.ContextTools(root).check_map({}).startswith("The map is current: 3 rows cover all 3 paths")


def test_check_map_asks_only_for_descriptions_when_coverage_is_complete(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    write(root, "app.py")
    write(root, "maps/project-map.md", map_rows(("app.py", "Describe manually.", "-"), ("maps/", "Maps.", "-"),
                                                ("maps/project-map.md", "Map.", "-")))
    text = server.ContextTools(root).check_map({})
    assert "Placeholder description (describe it):\n  - app.py" in text
    assert "--merge" not in text


def test_lowercase_marker_words_are_not_placeholders(tmp_path: Path) -> None:
    # Found in the Claude Desktop run: "Negative invariants (NI-xxx): ..." was reported as a placeholder.
    root = tmp_path / "proj"
    write(root, "a.py")
    write(root, "b.py")
    write(root, "c.py")
    write(root, "maps/project-map.md", map_rows(
        ("a.py", "Negative invariants (NI-xxx): rules for a todo list app.", "-"),
        ("b.py", "TODO: say what this does.", "-"),
        ("c.py", "Source file c.py (auto-generated entry; Describe Manually).", "-"),
        ("maps/", "Maps.", "-"), ("maps/project-map.md", "Map.", "-"),
    ))
    text = server.ContextTools(root).check_map({})
    flagged = text.split("Placeholder description (describe it):\n", 1)[1].split("\nDescribe each", 1)[0]
    assert flagged.splitlines() == ["  - b.py", "  - c.py"]


def test_rule_scopes_match_the_verifier_on_this_repository() -> None:
    text = (ROOT / "invariants" / "negative-invariants.md").read_text(encoding="utf-8")
    rules = server._rule_blocks(text)
    assert len(rules) >= 8
    files = verify.iter_python_files(ROOT, [])
    for rule in rules:
        if rule["type"] == "required-text":
            continue
        scope, exclude = rule.get("scope", ["**/*.py"]), rule.get("exclude", [])
        for path in files:
            expected = verify.matches_any(path, scope) and not verify.matches_any(path, exclude)
            assert server.rule_covers(rule, path) is expected, (rule["id"], path)


def invariant_project(tmp_path: Path) -> Path:
    root = tmp_path / "proj"
    write(root, "app/cart.py", "x = 1\n")
    write(root, "app/net.py", "import requests\n")
    write(root, "invariants/negative-invariants.md", """# Invariants

### NI-100: No `eval` in application code

- **Never:** call `eval()` in `app/`.
- **Safe alternatives:** parse values with `int()`.

```invariant-rule
{"id": "NI-100", "type": "forbidden-call", "description": "No eval in app.", "calls": ["eval"], "scope": ["app/**/*.py"]}
```

### NI-101: Network calls go through app/net.py

```invariant-rule
{"id": "NI-101", "type": "isolated-import", "description": "Only net.py imports requests.", "modules": ["requests"], "allowed_in": ["app/net.py"], "use": "app/net.py", "scope": ["app/**/*.py"]}
```

### NI-102: The cart keeps its rounding guard

- **Never:** remove the guard.
""")
    write(root, "decisions/0001-files.yaml", "id: ADR-0001\ntitle: Plain files, no database\n")
    write(root, "maps/project-map.md", map_rows(("app/cart.py", "Cart.", "NI-102"), ("app/net.py", "Net.", "-")))
    return root


def test_invariants_come_from_scope_even_when_the_map_lists_none(tmp_path: Path) -> None:
    tools = server.ContextTools(invariant_project(tmp_path))
    text = tools.get_invariants_for_file({"file_path": "app/net.py"})
    assert "- NI-100: No `eval` in application code (its scope covers this path)" in text
    assert "    Here: must not call: eval" in text
    assert "    - **Safe alternatives:** parse values with `int()`." in text
    assert "- NI-101: Network calls go through app/net.py (its scope covers this path)" in text
    assert "    Here: this file is the one place allowed to import requests" in text
    assert "- ADR-0001: Plain files, no database" in text


def test_listed_narrative_invariants_and_wrappers(tmp_path: Path) -> None:
    tools = server.ContextTools(invariant_project(tmp_path))
    text = tools.get_invariants_for_file({"file_path": "app/cart.py"})
    assert "- NI-102: The cart keeps its rounding guard (listed in maps/project-map.md)" in text
    assert "    - **Never:** remove the guard." in text
    assert "    Here: do not import requests here; use app/net.py" in text
    assert text.index("NI-102") < text.index("NI-100")  # the map's own IDs come first


def test_a_path_no_invariant_covers(tmp_path: Path) -> None:
    root = invariant_project(tmp_path)
    write(root, "README.md", "# x\n")
    text = server.ContextTools(root).get_invariants_for_file({"file_path": "README.md"})
    assert "No invariant covers this path" in text


def test_undefined_ids_and_decisions_are_kept_apart(tmp_path: Path) -> None:
    root = invariant_project(tmp_path)
    write(root, "maps/project-map.md", map_rows(("app/cart.py", "Cart.", "NI-404")))
    text = server.ContextTools(root).get_invariants_for_file({"file_path": "app/cart.py"})
    assert "- NI-404: no definition found (listed in maps/project-map.md)" in text
    decisions = text.split("Project-wide decisions (they apply to every file):\n", 1)[1]
    assert decisions.startswith("- ADR-0001: Plain files, no database")
    assert "NI-100" not in decisions and "NI-102" not in decisions  # invariants are not decisions
    assert text.endswith("Check the code with: python scripts/verify_invariants.py app/cart.py")


def test_rule_detail_for_every_rule_type() -> None:
    detail = server.rule_detail
    assert detail({"type": "forbidden-import", "forbidden": ["a", "b"]}, "x.py") == "must not import: a, b"
    assert detail({"type": "forbidden-import", "forbidden": ["a"], "allow_in": ["x.py"]}, "x.py") == "this file is exempt (allow_in)"
    assert detail({"type": "forbidden-call", "calls": ["eval"], "allow_in": ["tools/*.py"]}, "tools/t.py") == "this file is exempt (allow_in)"
    assert detail({"type": "forbidden-call", "calls": ["eval"], "allow_in": ["tools/*.py"]}, "app/t.py") == "must not call: eval"
    assert detail({"type": "stdlib-only"}, "x.py") == "standard library only"
    assert detail({"type": "stdlib-only", "allow": ["yaml", "attrs"]}, "x.py") == "standard library only (also allowed: yaml, attrs)"
    assert detail({"type": "isolated-import", "modules": ["requests"], "allowed_in": ["net.py"]}, "a.py") == \
        "do not import requests here; use net.py"
    assert detail({"type": "custom"}, "x.py") == "rule type custom"


def test_rule_scope_defaults_to_python_files() -> None:
    rule = {"id": "NI-1", "type": "forbidden-call", "calls": ["eval"]}
    assert server.rule_covers(rule, "deep/pkg/mod.py") and not server.rule_covers(rule, "README.md")


def test_ignore_rules_apply_to_everything_below_an_ignored_directory(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    write(root, ".agentignore", "build/\nsecret\n")
    rules = server.IgnoreRules(root)
    assert rules.ignored("build/sub/out.txt", False)        # parent directory matches a dir-only rule
    assert rules.ignored("build", True) and not rules.ignored("build", False)
    assert rules.ignored("a/secret/key.txt", False)         # an unanchored name matches at any depth
    assert not rules.ignored("a/secrets.txt", False)
    assert not rules.ignored("src/app.py", False)
    assert rules.ignored(".git/config", False)              # always ignored


def test_check_map_on_stale_rows_only(tmp_path: Path) -> None:
    root = tmp_path / "proj"
    write(root, "maps/project-map.md", map_rows(("gone.py", "Gone.", "-"), ("maps/", "Maps.", "-"),
                                                ("maps/project-map.md", "Map.", "-")))
    text = server.ContextTools(root).check_map({})
    assert "Stale row (the path is gone):\n  - gone.py" in text and "--merge" in text
    assert "No row" not in text and "Placeholder" not in text


def test_required_text_rules_cover_only_their_file() -> None:
    rule = {"id": "NI-9", "type": "required-text", "file": "a/b.py", "contains": ["MARK"]}
    assert server.rule_covers(rule, "a/b.py") and not server.rule_covers(rule, "a/c.py")
    assert server.rule_detail(rule, "a/b.py") == "this file must keep: 'MARK'"


def test_the_new_tools_are_listed_and_dispatched(tmp_path: Path) -> None:
    tools = server.ContextTools(invariant_project(tmp_path))
    listed = server.handle_message({"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, tools)
    names = [tool["name"] for tool in listed["result"]["tools"]]
    assert names == ["read_project_map", "get_file_purpose", "get_invariants_for_file", "check_map"]
    reply = server.handle_message({"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                                   "params": {"name": "get_invariants_for_file", "arguments": {"file_path": "app/cart.py"}}}, tools)
    assert reply["result"]["isError"] is False and "NI-100" in reply["result"]["content"][0]["text"]
    bad = server.handle_message({"jsonrpc": "2.0", "id": 3, "method": "tools/call",
                                 "params": {"name": "get_invariants_for_file", "arguments": {}}}, tools)
    assert bad["error"]["code"] == server.INVALID_PARAMS
    json.dumps(listed)  # every schema stays serializable
