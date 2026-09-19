# AGENTS.md — Operating Manifesto for AI Agents

This file is the primary contract between this repository and any AI coding agent
(Claude Code, Cursor, GitHub Copilot, Codex, Gemini CLI, and similar tools).
`CLAUDE.md` is a byte-identical mirror of this file; edit `AGENTS.md` and re-copy it.

Read this file completely before you change anything. It is short on purpose.

## The Four Rules

### Rule 1 — Read the map before you search

Read `maps/project-map.md` **before** running any exploratory `grep`, `find`, `ls -R`,
or whole-directory read. The map lists every tracked file with its category, purpose, and
the invariants that protect it. Use it to jump straight to the file you need.

- If your MCP client exposes `read_project_map` and `get_file_purpose`, prefer them.
- Only fall back to searching when the map has no entry for what you need. When that
  happens, the map is incomplete: add the missing entry as part of your change.
- Never read paths excluded by `.agentignore`; they are noise for your context window.

### Rule 2 — A bug is not fixed until a regression test proves it

Never declare a bug fixed without an automated regression test that:

1. fails on the buggy code, and
2. passes on the fixed code, and
3. survives **mutation verification**:

```bash
python scripts/mutation_guard.py --test tests/test_example.py --target src/module.py:function_name
```

The guard mutates the target function and requires the test to fail. A test that stays
green while the function is broken is a mock, not a test, and it does not count.

### Rule 3 — Ask before anything destructive or irreversible

Stop and obtain **explicit user consent in the chat** before you run any operation that
cannot be undone, including:

- `git push --force`, `git reset --hard`, `git clean -fd`, branch or tag deletion
- deleting, truncating, or overwriting user data, or wiping files and directories
- dropping data stores, rewriting history, or mass-renaming files

Approval for one destructive action does not extend to the next. If in doubt, ask.

### Rule 4 — Zero unauthorized dependencies

Prefer the language standard library. Do not add a third-party package, service, or
system tool unless the user approved it in this conversation. Dependency additions are
audited by `python scripts/check_dependency_budget.py` and by CI.

## Negative Invariants and Decisions

- `invariants/negative-invariants.md` lists what you must **not** refactor, remove, or
  "simplify" — guards that look redundant but encode a past failure.
- `decisions/*.yaml` holds machine-readable architecture decisions. Each has
  `forbidden_actions`. If a task requires one of them, stop and ask the user.
- Files whose map entry lists an invariant ID (for example `NI-006`) require you to read
  that invariant first.
- Never delete an `INVARIANT(...)` marker comment.

## Working Agreements

- Keep changes minimal and local. Do not reformat, rename, or reorganize code you were
  not asked to touch.
- When you add, move, or delete a file, update `maps/project-map.md` in the same change.
- Verify before you claim success, and report failures verbatim.
- Write documentation, comments, and messages in clear, idiomatic English.

## Commands

| Purpose                        | Command                                              |
| ------------------------------ | ---------------------------------------------------- |
| Run the self-guarding tests    | `python -m pytest -q tests`                          |
| Check that the map is current  | `python scripts/init_mapping.py --check`             |
| Add new files to the map       | `python scripts/init_mapping.py --merge`             |
| Verify architectural invariants| `python scripts/verify_invariants.py`                |
| Audit the dependency budget    | `python scripts/check_dependency_budget.py`          |
| Verify a regression test       | `python scripts/mutation_guard.py --help`            |
| Install the git pre-commit hook| `sh scripts/install_hooks.sh`                        |

## Claude Code Integration

- Slash commands in `.claude/commands/`: `/verify-map`, `/verify-invariants`, `/mutation-test`,
  and `/diet-check`. They run the scripts above and explain how to act on the result.
- Hooks in `.claude/settings.json` run automatically. After you edit a `.py` file, the invariant
  checker runs and feeds violations back to you; fix the code, never the rule. Before a
  `git commit`, the dependency budget and the map test must pass.
- Keep this file short. Detail belongs in the map, `invariants/`, `decisions/`, or `docs/`.

## Definition of Done

A change is done only when: the map is current, `pytest` passes, `verify_invariants.py`
and `check_dependency_budget.py` exit 0, every bug fix has a mutation-verified regression
test, and no destructive action was taken without consent.
