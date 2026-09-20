# AGENTS.md: Operating Manifesto for AI Agents (TypeScript)

This file is the contract between this repository and any AI coding agent (Claude Code, Cursor,
GitHub Copilot, Codex, and similar tools). Copy it to `CLAUDE.md` unchanged so Claude Code finds
it too; the map test fails if the two files differ.

Read this file completely before you change anything.

## The Five Rules

### Rule 1: Read the map before you search

Read `maps/project-map.md` **before** running exploratory `grep`, `find`, or `ls -R`. It lists
every file with its category, purpose, and protecting invariants. Search only when the map has
no entry for what you need, and then add the missing entry as part of your change.
Never read paths excluded by `.agentignore` (`node_modules/`, `dist/`, lockfiles, coverage).

### Rule 2: A bug is not fixed until a regression test proves it

Every bug fix needs an automated vitest (or jest) regression test that fails on the buggy code
and passes on the fixed code. Then prove the test can fail with **manual mutation
verification**:

1. Note the current state of the function (commit or stash your fix first).
2. Temporarily break the function: invert a condition, change an operator, or make it return
   `undefined`.
3. Run the test. It **must fail**. If it stays green, the test does not guard the function;
   rewrite it.
4. Restore the function exactly, and re-run the test to confirm it passes again.

If the user approves a dev dependency, StrykerJS automates this. Without that approval, use the
manual steps above. Do not leave a mutated file behind.

### Rule 3: Ask before anything destructive or irreversible

Obtain explicit user consent in the chat before `git push --force`, `git reset --hard`,
deleting or overwriting user data, wiping files, running destructive migrations, or rewriting
history. Approval for one action does not extend to the next.

### Rule 4: Zero unauthorized dependencies

Prefer the platform and the packages already in `package.json`. Do not run `npm install <pkg>`
or edit `dependencies` or `devDependencies` unless the user approved it in this conversation.
Node's built-in modules (`node:fs`, `node:path`, `node:test`) come first.

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

## TypeScript Conventions

- Keep `strict` type checking green; never silence errors with `any` or `@ts-ignore` to make a
  build pass.
- Prefer small pure functions and explicit return types on exported functions.
- Mock only real boundaries (network, timers, file system). Never mock the module under test.
- Do not reformat or reorganize code you were not asked to touch.

## Commands

| Purpose                          | Command                                                 |
| -------------------------------- | ------------------------------------------------------- |
| Run all tests                    | `npx vitest run`  (or `npx jest`)                       |
| Type-check                       | `npx tsc --noEmit`                                      |
| Run the map coverage test        | `npx vitest run tests/test_maps.test.ts`                |
| Check that the map is current    | `python scripts/init_mapping.py --check`                |
| Add new files to the map         | `python scripts/init_mapping.py --merge`                |
| Verify architectural invariants  | `python scripts/verify_invariants.py` (Python sources)  |
| Audit the dependency budget      | `python scripts/check_dependency_budget.py`             |

The scripts in `scripts/` are standard-library Python and work on any repository; they do not
add a Python dependency to a TypeScript project.

## Definition of Done

The map is current, the test suite and type check pass, the dependency budget holds, every bug
fix has a manually mutation-verified regression test, and no destructive action happened
without consent.
