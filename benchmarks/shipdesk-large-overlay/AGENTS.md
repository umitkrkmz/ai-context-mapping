# AGENTS.md: Operating Manifesto for AI Agents (Python)

This file is the contract between this repository and any AI coding agent (Claude Code, Cursor,
GitHub Copilot, Codex, and similar tools). Copy it to `CLAUDE.md` unchanged so Claude Code finds
it too; `tests/test_maps.py` fails if the two files differ.

Read this file completely before you change anything.

## The Five Rules

### Rule 1: Read the map before you search

Read `maps/project-map.md` **before** running exploratory `grep`, `find`, or `ls -R`. It lists
every file with its category, purpose, and protecting invariants. Search only when the map has
no entry for what you need, and then add the missing entry as part of your change.
Never read paths excluded by `.agentignore`.

### Rule 2: A bug is not fixed until a regression test proves it

Every bug fix needs an automated pytest regression test that fails on the buggy code and passes
on the fixed code. Then prove the test can fail:

```bash
python scripts/mutation_guard.py --test tests/test_example.py --target src/package/module.py:function_name
```

The guard breaks the function and requires the test to go red. A test that stays green while
the function is broken does not count.

### Rule 3: Ask before anything destructive or irreversible

Obtain explicit user consent in the chat before `git push --force`, `git reset --hard`,
deleting or overwriting user data, wiping files, dropping data stores, or rewriting history.
Approval for one action does not extend to the next.

### Rule 4: Zero unauthorized dependencies

Use the Python standard library. Do not add a package to `requirements*.txt` or
`pyproject.toml`, and do not import one, unless the user approved it in this conversation.
`python scripts/check_dependency_budget.py` audits this.

### Rule 5: Do not invent project knowledge

Never fill architectural gaps with plausible fiction. If an invariant, decision, or map entry
does not clearly define a constraint or contract, **stop and ask the user** instead of assuming.
Cite your source (a map row, an invariant or decision ID, or code you read) for every constraint
you rely on, and say "I do not know" when you do not.

## Negative Invariants and Decisions

- `invariants/negative-invariants.md` lists code you must not remove or simplify. Never delete
  an `INVARIANT(...)` marker. A guard that looks redundant encodes a past bug until proven
  otherwise (use `git log -S` and `git blame`).
- `decisions/*.yaml` records architecture decisions. Never take an action listed in a
  decision's `forbidden_actions`; stop and ask the user.
- If the map lists an invariant ID for a file, read that entry before editing the file.

## Python Conventions

- Target the Python version declared in the project; do not use newer syntax than it allows.
- Add type hints and short docstrings to new public functions.
- Keep functions small and pure where possible so they are testable without mocks.
- Mock only real boundaries (network, clock, randomness). Never mock the code under test.
- Do not reformat or reorganize code you were not asked to touch.

## Commands

| Purpose                         | Command                                              |
| ------------------------------- | ---------------------------------------------------- |
| Run all tests                   | `python -m pytest -q`                                |
| Check that the map is current   | `python scripts/init_mapping.py --check`             |
| Add new files to the map        | `python scripts/init_mapping.py --merge`             |
| Verify architectural invariants | `python scripts/verify_invariants.py`                |
| Audit the dependency budget     | `python scripts/check_dependency_budget.py`          |
| Verify a regression test        | `python scripts/mutation_guard.py --help`            |

## Definition of Done

The map is current, `pytest` passes, `verify_invariants.py` and `check_dependency_budget.py`
exit 0, every bug fix has a mutation-verified regression test, and no destructive action
happened without consent.
