---
description: Prove a regression test can fail by temporarily mutating the Python function it protects. Use after fixing a bug, before calling it fixed.
argument-hint: "--test <test file> --target <file.py:function> [options]"
---

Verify a regression test with `mutation_guard.py` (AGENTS.md Rule 2). The guard temporarily breaks the
target function and requires the test to fail. A test that stays green while the function is broken
proves nothing.

Use `python3` to run Python; if that command is missing or fails, use `python`. Run from
`${CLAUDE_PROJECT_DIR}`. Use the project's own `scripts/mutation_guard.py` when it exists, otherwise
`${CLAUDE_PLUGIN_ROOT}/scripts/mutation_guard.py`.

Arguments given: `$ARGUMENTS`

If arguments were given, run `mutation_guard.py $ARGUMENTS`. Otherwise work out the parameters:

1. `--test`: the test file that covers the bug fix. Find it through `maps/project-map.md` when the
   project has one.
2. `--target`: the function the fix changed, as `path/to/file.py:function_name`, or
   `path/to/file.py:ClassName.method` for a method.
3. Run `mutation_guard.py --test <test> --target <target>`.

Useful options:

| Option | Use it to |
| ------ | --------- |
| `--list` | Preview the mutants without running any tests or touching files |
| `--min-score 0.8` | Require a higher share of mutants to be killed (default 0.5) |
| `--max-mutants N` | Cap the number of mutants on large functions (default 30) |
| `--operators compare,boundary` | Restrict the operators (`compare`, `boundary`, `arith`, `bool`, `not`, `if`, `return`, `const`) |
| `--runner "python -m unittest {test}"` | Use a test runner other than pytest |
| `--timeout SEC` | Change the per-run timeout (default 120; a timeout counts as killed) |
| `--recover` | Restore the target from a leftover `.mgbak` backup after an interrupted run |

Interpreting the result (exit code 0 = pass, 1 = verification failed, 2 = usage or environment error):

- `neutralize` survived: the test still passes when the function does nothing. Rewrite it to assert on
  real output instead of mocking the behavior away.
- A `boundary shift` mutant survived (`>=` became `>`): add cases at, one below, and one above the edge.
- Other mutants survived: strengthen the assertions for each survivor, or explain why that mutant is
  equivalent (changes no observable behavior).
- Exit 2 with "baseline run failed": the test fails before any mutation. Fix the test or the code first.

Rules:

- The tool rewrites the target file while it runs. Do not edit that file, and do not run two guards on it
  at once. After an interrupted run, use `--recover`.
- Report the mutation score and every survivor in your final message.
- Only Python targets can be mutated.
