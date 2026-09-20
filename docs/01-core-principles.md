# Core Principles

This document explains **why** the framework is shaped the way it is. If you only want to use
it, start with the [README](../README.md). If you want to change it, read this first: several
choices that look arbitrary are load-bearing.

## 1. The problem: three ways AI agents hurt a codebase

Large language models are fast and fluent, and they work with a small, forgetful window of
context. Three failure modes follow directly from that.

| Failure mode                    | What happens                                                                 | Typical cost                                      |
| ------------------------------- | ---------------------------------------------------------------------------- | ------------------------------------------------- |
| **Context drift**               | The agent's picture of the project diverges from reality: wrong file, stale API, invented structure. | Plausible code that does not fit the codebase.    |
| **Token waste**                 | The agent explores by reading or grepping widely to orient itself.           | Money, latency, and a window full of noise that crowds out the task. |
| **Accidental destructive change** | The agent "simplifies" a guard, deletes a "dead" branch, or reaches for `--force`. | Regressions of bugs that were already fixed once. |

The framework answers each with a cheap, boring, verifiable mechanism rather than a cleverer
prompt.

| Failure mode                | Mechanism                                                        |
| --------------------------- | ---------------------------------------------------------------- |
| Context drift               | A project map that a test forces to stay true                    |
| Token waste                 | The map as a routing table, plus `.agentignore`                  |
| Accidental destructive change | Negative invariants, machine-readable decisions, static checks, and mutation-verified tests |

## 2. The token diet

Every token an agent spends on orientation is a token not spent on the task. The cost is not
only financial:

- **Attention dilution.** Relevant facts compete with irrelevant ones inside the window.
- **Latency.** More input means slower turns.
- **Drift risk.** The more unrelated code the agent has seen, the more likely it is to borrow
  from the wrong place.

The diet has three rules.

1. **Route, don't scan.** A map states each file's purpose in one line. The agent reads the
   map (about a thousand tokens) and then opens the one or two files that matter. See the
   [calculator](02-token-diet-calculator.md) for the arithmetic.
2. **Exclude the unreadable.** `.agentignore` removes build output, lockfiles, binaries, logs,
   and bulk data. These files carry almost no signal per token and can be enormous.
3. **Keep the map small.** `scripts/init_mapping.py` collapses directories with many sibling
   files into a single `dir/**` row, so a repository can grow without its map growing
   proportionally.

A map that is too long defeats its purpose. If yours passes a few thousand tokens, group
more aggressively rather than trimming descriptions.

> **Measured caveat.** In [two A/B experiments](benchmark-results.md), unguided agents did not scan
> repositories: they listed files and grepped, and their cost did not grow with project size up to
> 55,600 tokens. The token diet is a hypothesis for much larger repositories and for tasks that
> cannot be found by searching, not a demonstrated saving. What the framework did deliver was
> verification evidence (mutation-checked tests, invariant checks) at a small, roughly constant cost.

## 3. Why a file-based store

[`decisions/0001-no-database-file-store.yaml`](../decisions/0001-no-database-file-store.yaml)
records the decision to keep all state in plain files. The reasons apply to the framework and
to the projects that adopt it.

- **Reviewable.** A change to state is a diff a human can read in a pull request.
- **Greppable and readable by agents.** No client, driver, or query language is needed to see
  the data. An agent can inspect the whole state with the tools it already has.
- **Portable and dependency-free.** Nothing to install, migrate, back up, or authenticate to.
  This is what makes Rule 4 (zero unauthorized dependencies) achievable.
- **Transparent to version control.** History, blame, and revert work on the data itself.
- **Small blast radius.** A bug in file handling corrupts one file that can be restored from
  git, not an opaque store.

The costs are real: linear scans, no transactions, no concurrent writers. The decision
therefore states its own exit condition. If requirements outgrow files, write a new record
that supersedes it and get explicit approval first. Choosing a file store is a bet on
scale, and the record makes the bet visible.

The same reasoning explains why the guardrails themselves are Markdown and YAML:

- the **map** is a Markdown table,
- the **invariants** are Markdown with embedded JSON rule blocks,
- the **decisions** are flat YAML,

and all of it can be parsed with the Python standard library.

## 4. The guardrail layers

No single control is enough. Prompts get ignored, tests get mocked, humans get tired. The
framework stacks independent layers so that a mistake must slip through several of them.

```text
  Layer 6   CI                    same checks, on every push, cannot be skipped locally
  Layer 5   Pre-commit hook       fast checks before a commit exists
  Layer 4   Mutation guard        proves a regression test can actually fail
  Layer 3   Static invariants     AST rules: forbidden imports, isolated wrappers, required guards
  Layer 2   Negative invariants   what must not change, and why (prose + machine rules)
            + Decisions           what must not be introduced (forbidden_actions)
  Layer 1   Project map (MCP)     where things are; which invariants apply to each file
  Layer 0   Agent manifesto       AGENTS.md / CLAUDE.md / Copilot / Cursor rules: the five rules
```

| Layer | Fails when                                            | Enforced by                                  |
| ----- | ----------------------------------------------------- | -------------------------------------------- |
| 0     | The agent ignores instructions                        | (advisory) reinforced by every layer below   |
| 1     | The map is incomplete or stale                        | `tests/test_maps.py`, `init_mapping.py --check` |
| 2     | A protected guard or forbidden action is touched      | `verify_invariants.py` rules; human review   |
| 3     | An import or call crosses a boundary                  | `verify_invariants.py`                       |
| 4     | A test stays green when the code is broken            | `mutation_guard.py`                          |
| 5     | Any of layers 1-3 fail locally                        | `install_hooks.sh` hook                      |
| 6     | Any check fails on the server                         | `.github/workflows/ai-guardrails.yml`        |

Layer 0 is the only advisory layer, and that is deliberate. Everything an instruction says
that matters is also checked by a script, so a distracted or non-compliant agent still hits a
wall.

### Design properties shared by every layer

- **Deterministic.** Static checks and tests give the same answer every run. No model is asked
  to judge another model.
- **Fast.** The whole set runs in seconds so that it runs on every commit.
- **Actionable failures.** Each failure names the path and prints the exact command or edit
  that fixes it. An agent can recover without asking.
- **Standard library only.** Guardrails must never become the supply-chain risk they exist to
  prevent (NI-001).

## 5. Negative invariants

Positive requirements ("the response contains a request ID") are covered by ordinary tests.
The dangerous knowledge is negative: *do not remove the guard that stops the double-delete;
do not merge these two branches.* Nothing fails when such code disappears until the original
bug returns in production.

The framework turns that knowledge into data:

1. A **narrative entry** gives the invariant an ID and explains why the code exists.
2. A **machine rule** (forbidden import, isolated wrapper, forbidden call, required text) makes
   violations fail a script.
3. An **`INVARIANT(NI-xxx)` marker** in the code, together with a `required-text` rule, makes
   *deleting the guard* a failure.
4. The **map** lists the ID next to the file, so the agent sees it before editing.

The default assumption for any unexplained guard is that it encodes a past incident. The
burden of proof is on the deleter. See
[`invariants/negative-invariants.md`](../invariants/negative-invariants.md).

## 6. Mutation-verified regression tests

Rule 2 says a bug is not fixed without a regression test. Agents, like people, are capable of
writing a test that passes for the wrong reason: it mocks the function under test, asserts on
a constant, or never reaches the changed line. The mutation guard closes that loophole. It
breaks the function on purpose (most importantly by replacing the whole body with `return
None`) and demands that the test turn red. A test that cannot fail is not evidence.

Mutation testing is normally a heavyweight practice. Here it is applied narrowly: one test
file, one function, at most a few dozen mutants. That keeps it cheap enough to be a routine
step for every bug fix.

## 7. Consent for irreversible actions

Rule 3 exists because the failure is asymmetric: asking costs seconds, a force-push over
shared history can cost days. The rule is intentionally blunt and lists examples rather than
trying to define "destructive" precisely. When in doubt, ask, and treat approval for one
action as approval for that action only.

## 8. Trade-offs and non-goals

- **The map needs upkeep.** That is the price of the token diet. The test makes upkeep
  unavoidable, and `init_mapping.py --merge` makes it a one-command chore.
- **Static analysis is Python-only.** `verify_invariants.py` reads Python with `ast`. For other
  languages, use the map, invariants prose, `required-text` rules on non-Python files, and your
  language's own import-boundary linter, and record the rule in the same document.
- **Dynamic imports built from variables are invisible.** Constant-string dynamic imports are
  caught; computed ones are not. Ban `eval`/`exec` (NI-005) and review the rest.
- **Not a security boundary.** These are guardrails against mistakes, not a sandbox against a
  hostile agent.
- **Not a replacement for review.** They remove the boring failures so that review time goes
  to design.

## 9. Design rules for extending the framework

1. New checks must be deterministic, stdlib-only, and fast.
2. Every failure message must say what is wrong and how to fix it.
3. Every new file must appear in `maps/project-map.md` (the test will insist).
4. Prefer a new rule type or a new invariant entry over a new script.
5. Record irreversible architectural choices as a decision record, not in a commit message.
