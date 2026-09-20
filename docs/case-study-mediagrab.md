# Case Study: MediaGrab

MediaGrab is a media-downloading tool built with AI pair programming. It is the reference
project for this framework and shows it under realistic pressure: many small modules,
platform-specific edge cases, and an AI agent making changes regularly.

> **About this document.** It describes the *shape* of the MediaGrab architecture and how each
> guardrail applied to it. The project's headline facts are its zero-database design, its
> suite of 100+ unit tests, and its map-guided AI collaboration. Module names and code
> snippets below are representative illustrations of that architecture, not an excerpt of the
> repository. Replace them with your own when you write your case study, and measure your own
> token and regression numbers with the method in
> [02-token-diet-calculator.md](02-token-diet-calculator.md).

## 1. The situation

A downloader is a magnet for the failures this framework targets:

- **Edge cases everywhere.** Rate limits, partial downloads, odd filenames, platform path
  limits, and providers that change behavior. Each edge case tends to be handled by a small
  guard that looks arbitrary in isolation.
- **Fast, AI-driven iteration.** Features arrived in short sessions with an agent that had
  never seen the code before. Every session started cold.
- **A user-facing data set.** Download history, queues, and settings that must never be lost
  or corrupted by a clever refactor.

Without guardrails the failure pattern is a familiar one: the agent spends the first part of
each session grepping to find its bearings, then "cleans up" a guard that existed for a
reason, and the bug comes back.

## 2. The architecture

Three decisions shaped everything else.

### Zero database, plain-file store

All state (queue, history, settings) lives in JSON and line-oriented text files under one
data directory. There is no database engine, no ORM, and no background service. This is
[ADR-0001](../decisions/0001-no-database-file-store.yaml) in this repository, generalized.

Consequences of this choice:

- **State is inspectable by the agent.** To debug a queue problem the agent reads a file,
  instead of needing a driver and a query.
- **Tests are trivial to isolate.** A test points the store at a temporary directory; there is
  no service to start and nothing to tear down.
- **All writes go through one wrapper.** Atomic write-then-rename lives in a single module. An
  `isolated-import`/`forbidden-call` rule makes any other write path fail the static check,
  so a partially written history file cannot happen by accident.
- **Corruption has a small blast radius.** One damaged file is restored from backup or git;
  there is no opaque store to repair.

### Layered modules with one-way dependencies

```text
  cli / ui  ->  services (queue, history)  ->  providers (per-site adapters)  ->  net wrapper
                          \                                                        |
                           ->  store (atomic file wrapper)  <----------------------
```

Each arrow is a permitted import; the reverse direction is forbidden by a `forbidden-import`
rule. The network wrapper and the store wrapper are the only modules allowed to touch the
outside world, expressed as `isolated-import` rules. Provider adapters cannot reach around
them.

### Guards as documented, protected code

Edge-case handling is concentrated in small named functions (path safety, retry policy,
filename sanitizing). Each carries an `INVARIANT(NI-xxx)` marker and a `required-text` rule,
and is listed against its file in the project map.

## 3. How each guardrail was applied

| Guardrail                | Application in MediaGrab                                                            |
| ------------------------ | ----------------------------------------------------------------------------------- |
| `AGENTS.md`              | Five rules loaded at the start of every session by Claude Code, Cursor, and Copilot. |
| Project map + MCP server | The agent asks `get_file_purpose` instead of grepping; the map names the guard modules and their invariants. |
| `.agentignore`           | Excluded downloaded media, logs, sample datasets, and build output from context.    |
| Negative invariants      | One entry per platform quirk: long Windows paths, `Retry-After` handling, filename sanitizing. |
| Decision records         | Zero-DB, standard-library-first, no background daemon.                              |
| `verify_invariants.py`   | Enforced layer direction, the two wrappers, and the stdlib-only rule.               |
| Mutation guard           | Run on every bug-fix test, against the function that was fixed.                     |
| Pre-commit hook and CI   | The same commands, blocking merges.                                                 |

## 4. The test suite as the safety net

The project's unit suite has more than 100 tests. Three properties made it trustworthy enough
to refactor against:

1. **Pure functions at the core.** Parsing, path building, retry timing, and filename rules
   are pure and take their inputs as arguments, so tests need no mocks for them.
2. **Boundaries mocked narrowly.** Only the network wrapper and the clock are substituted. The
   code under test is never mocked.
3. **Mutation-verified fixes.** A regression test for a fixed bug had to kill the
   neutralize mutant of the repaired function. This catches the two classic bad regression
   tests: ones that patch the function under test, and ones that assert on a value that
   never depended on the fix.

## 5. A representative bug-fix session

This is the workflow the agent followed, with the guardrails in the loop.

1. **Orient.** The agent calls `read_project_map`. It sees `storage/paths.py` listed with
   invariant `NI-101` and reads that entry: the long-path prefix must stay. About a thousand
   tokens, no grep.
2. **Reproduce.** It writes `test_paths_over_260_chars_are_prefixed`, and it fails on the
   current code for the expected reason.
3. **Fix.** A minimal change to `safe_path()`. The test passes.
4. **Verify the test.**

   ```bash
   python scripts/mutation_guard.py --test tests/test_paths.py --target storage/paths.py:safe_path
   ```

   The neutralize mutant is killed, and so are the inverted comparisons.
5. **Guard the guard.** The agent leaves the `INVARIANT(NI-101)` marker in place; the
   `required-text` rule would fail the commit if it were removed.
6. **Commit.** The hook runs the invariant check, the dependency budget, and the map test.
   The agent added no dependency and no untracked file.

## 6. What changed

The results the project attributes to the framework, in the order they were noticed:

- **Regressions stopped recurring.** Fixed bugs stayed fixed, because each fix came with a
  mutation-verified test and each protective guard came with an invariant. The refactors that
  used to reintroduce old bugs were now blocked by a failing check or a test, not by luck.
- **Sessions started faster.** The agent oriented from the map instead of a repository
  crawl, which also left more of the window for the actual task.
- **Reviews focused on design.** Structural mistakes (a provider importing the store
  directly, a stray third-party import) were caught by scripts before a human saw the diff.
- **Onboarding a new agent or contributor cost minutes.** `AGENTS.md`, the map, and the
  invariants together are a complete orientation.

Treat the qualitative claims above as the project's reported experience. If you adopt the
framework, record your own before-and-after: regressions per release, tokens per task, and
review comments about structure.

## 7. Lessons that generalize

1. **Put the guard's *reason* next to the guard.** An agent that can read why a branch exists
   will leave it alone; one that cannot will optimize it away.
2. **Enforce boundaries with imports, not conventions.** "Only the store writes files" is a
   sentence; a `forbidden-call` rule is a fact.
3. **Prove tests can fail.** Coverage numbers say a line ran; mutation results say the test
   noticed when it broke.
4. **Keep the map honest with a test, not a promise.** A map that can rot will.
5. **Prefer plain files.** Debuggability for humans and agents was worth more than any query
   power a database would have added.

## 8. Adopt the same setup

1. Copy the [template for your stack](../templates/) into your repository.
2. Run `python scripts/init_mapping.py`, then describe each row.
3. Write one negative invariant for the scariest guard in your code.
4. Run `sh scripts/install_hooks.sh`.
5. Register the [MCP server](../mcp/README.md) in your AI client.
