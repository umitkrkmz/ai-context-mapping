---
description: Prove a regression test can fail by mutating the function it protects
argument-hint: --test <test file> --target <file.py:function> [options]
allowed-tools: Bash(python scripts/mutation_guard.py *), Read
---

Verify a regression test with `scripts/mutation_guard.py` (AGENTS.md Rule 2). The guard
temporarily breaks the target function and requires the test to fail. A test that stays green
while the function is broken proves nothing.

Arguments given to this command: `$ARGUMENTS`

If arguments were given, run `python scripts/mutation_guard.py $ARGUMENTS`.

If none were given, work out the parameters yourself:

1. `--test`: the test file that covers the bug fix. Find it through `maps/project-map.md`,
   not with a repository-wide search.
2. `--target`: the function the fix changed, as `path/to/file.py:function_name`, or
   `path/to/file.py:ClassName.method` for a method.
3. Run `python scripts/mutation_guard.py --test <test> --target <target>`.

Useful options:

| Option | Use it to |
| ------ | --------- |
| `--list` | Preview the mutants without running any tests or touching files |
| `--min-score 0.8` | Require a higher share of mutants to be killed (default 0.5) |
| `--max-mutants N` | Cap the number of mutants on large functions (default 30) |
| `--operators compare,boundary` | Restrict the mutation operators (`compare`, `boundary`, `arith`, `bool`, `not`, `if`, `return`, `const`) |
| `--runner "python -m unittest {test}"` | Use a test runner other than pytest |
| `--timeout SEC` | Change the per-run timeout (default 120; a timeout counts as killed) |
| `--recover` | Restore the target from a leftover `.mgbak` backup after an interrupted run |

Interpreting the result (exit code 0 = pass, 1 = verification failed, 2 = usage or environment error):

- `neutralize` survived: the test still passes when the function does nothing. It does not
  exercise the function, or it mocks the behavior away. Rewrite it to assert on real output.
- A `boundary shift` mutant survived (`>=` became `>`): the test never checks the exact edge value.
  Add cases at, one below, and one above the boundary.
- Other mutants survived: strengthen the assertions for each `survivor` line, or explain in
  your report why that mutant is equivalent (changes no observable behavior).
- Exit 2 with "baseline run failed": the test fails before any mutation. Fix the test or the
  code first.

Rules:

- The tool rewrites the target file while it runs. Do not edit that file, and do not run two
  guards on it at once.
- If a run was interrupted and a `.mgbak` file remains, run the same command with `--recover`.
- Report the mutation score and every survivor in your final message.
- Only Python targets can be mutated. For other languages, follow the manual procedure in
  your template's `AGENTS.md`.
