---
description: Check this project's architectural invariants and decision records with the AST verifier, then fix violations without deleting rules. Use before committing changes to protected code.
argument-hint: "[file or directory ...]"
---

Run the invariant verifier and report the result.

Use `python3` to run Python; if that command is missing or fails, use `python`. Run from
`${CLAUDE_PROJECT_DIR}`. Use the project's own `scripts/verify_invariants.py` when it exists, otherwise
`${CLAUDE_PLUGIN_ROOT}/scripts/verify_invariants.py`.

Arguments given: `$ARGUMENTS`

Run `verify_invariants.py $ARGUMENTS`. With no arguments it checks the whole project; with paths it
checks only those files, and the `required-text` rules always run. To see which rules are active, add
`--list-rules`.

Exit codes: 0 = all invariants hold, 1 = violations found, 2 = configuration error.

For each violation the output names the rule ID, the file and line, and what is wrong. Fix the code so
that it obeys the rule, then run the verifier again and confirm it exits 0.

Rules:

- Never delete a rule, an `INVARIANT(...)` marker, or a `forbidden_imports` entry to make the check pass.
  Guards that look redundant encode past incidents (see `invariants/negative-invariants.md`).
- If the change genuinely requires breaking a rule, stop and ask the user. Do not work around it.
- Exit 2 means a rules file or decision record is malformed. Fix that file; do not skip the check.
- A `[warn]` about an unparsable file means a syntax error hides that file from the checks. Report it.
- A project without `invariants/negative-invariants.md` or `decisions/` has no rules. Say so, and offer
  `/ai-context-mapping:adopt`.
