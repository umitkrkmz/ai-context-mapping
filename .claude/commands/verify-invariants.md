---
description: Check architectural invariants and decision records with the AST verifier
argument-hint: [file or directory ...]
allowed-tools: Bash(python scripts/verify_invariants.py*)
---

Run the invariant verifier and report the result.

Arguments given to this command: `$ARGUMENTS`

Run `python scripts/verify_invariants.py $ARGUMENTS`. With no arguments it checks the whole
repository; with paths it checks only those files, and the `required-text` rules always run.

To see which rules are active, run `python scripts/verify_invariants.py --list-rules`.

Exit codes: 0 = all invariants hold, 1 = violations found, 2 = configuration error.

For each violation the output names the rule ID, the file and line, and what is wrong. Fix the
code so that it obeys the rule. Then run the verifier again and confirm it exits 0.

Rules:

- Never delete a rule, an `INVARIANT(...)` marker, or a `forbidden_imports` entry to make the
  check pass. Guards that look redundant encode past incidents (see
  `invariants/negative-invariants.md`).
- If the change genuinely requires breaking a rule, stop and ask the user. Do not work around
  it (AGENTS.md Rule 3).
- Exit 2 means a rules file or decision record is malformed. Fix that file; do not skip the check.
- A `[warn]` about an unparsable file means the file has a syntax error that hides it from
  the checks. Report it.
