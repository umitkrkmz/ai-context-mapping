# AGENTS.md: Operating Manifesto for AI Agents

This file is the contract between this repository and any AI coding agent (Claude Code, Cursor,
GitHub Copilot, Codex, and similar tools). Copy it to `CLAUDE.md` unchanged so Claude Code finds
it too.

Read this file completely before you change anything.

## The Four Rules

### Rule 1: Read the map before you search

Read `maps/project-map.md` **before** running exploratory `grep`, `find`, or `ls -R`. It lists
every file with its category, purpose, and protecting invariants. Search only when the map has
no entry for what you need, and then add the missing entry as part of your change.
Never read paths excluded by `.agentignore`.

### Rule 2: A bug is not fixed until a regression test proves it

Every bug fix needs an automated regression test that fails on the buggy code and passes on the
fixed code. Then prove the test can fail (mutation verification): temporarily break the function
under test (invert a condition, change an operator, make it return nothing), run the test, and
confirm it goes red. Restore the function exactly and confirm the test is green again.
For Python code, `python scripts/mutation_guard.py --test <test> --target <file>:<function>`
does this automatically and restores the file for you.

### Rule 3: Ask before anything destructive or irreversible

Obtain explicit user consent in the chat before `git push --force`, `git reset --hard`,
deleting or overwriting user data, wiping files, dropping data stores, or rewriting history.
Approval for one action does not extend to the next.

### Rule 4: Zero unauthorized dependencies

Prefer the language standard library. Do not add a package, service, or system tool unless the
user approved it in this conversation. `python scripts/check_dependency_budget.py` audits
`requirements*.txt`, `package.json`, and `pyproject.toml`.

## Negative Invariants and Decisions

- `invariants/negative-invariants.md` lists code you must not remove or simplify. Never delete
  an `INVARIANT(...)` marker. A guard that looks redundant encodes a past bug until proven
  otherwise (use `git log -S` and `git blame`).
- `decisions/*.yaml` records architecture decisions. Never take an action listed in a
  decision's `forbidden_actions`; stop and ask the user.
- If the map lists an invariant ID for a file, read that entry before editing the file.

## Working Agreements

- Keep changes minimal and local. Do not reformat or reorganize code you were not asked to touch.
- When you add, move, or delete a file, update `maps/project-map.md` in the same change.
- Verify before you claim success, and report failures verbatim.
- Document the build and test commands for this project in `README.md` and follow them.

## Guardrail Commands

| Purpose                         | Command                                              |
| ------------------------------- | ---------------------------------------------------- |
| Check that the map is current   | `python scripts/init_mapping.py --check`             |
| Add new files to the map        | `python scripts/init_mapping.py --merge`             |
| Verify architectural invariants | `python scripts/verify_invariants.py`                |
| Audit the dependency budget     | `python scripts/check_dependency_budget.py`          |

## Definition of Done

The map is current, the project's tests pass, the guardrail commands exit 0, every bug fix has a
mutation-verified regression test, and no destructive action happened without consent.
