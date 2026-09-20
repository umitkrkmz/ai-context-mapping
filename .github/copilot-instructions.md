# Copilot Instructions

These instructions apply to every Copilot Chat, Copilot Agent, and code-review request in
this repository. The full contract lives in [`AGENTS.md`](../AGENTS.md); this file
restates the parts that matter most at the IDE level.

## 1. Use the project map first

- Open `maps/project-map.md` before you search the workspace. It lists every file with its
  category, purpose, and protecting invariants.
- Do not run workspace-wide searches or attach whole directories as context when the map
  already points to the file you need.
- Never read paths matched by `.agentignore` (build output, virtual environments,
  `node_modules`, logs, binaries, bulk mock data).
- If you add, move, or delete a file, update `maps/project-map.md` in the same change.

## 2. Respect architectural invariants

- Before editing a file, check its `Invariants` column in the map. If it lists an ID such
  as `NI-006`, read that entry in `invariants/negative-invariants.md` first.
- Do not remove, "simplify", or reorder guards that carry an `INVARIANT(...)` marker, even
  if they look redundant.
- Read `decisions/*.yaml`. Never perform an action listed in a decision's
  `forbidden_actions`. Stop and ask the user instead.

## 3. Rules that always apply

1. **Regression tests for bug fixes.** A bug is fixed only when an automated regression
   test fails without the fix and passes with it. Verify with
   `python scripts/mutation_guard.py --test <test> --target <file>:<function>`.
2. **Consent for destructive actions.** Ask the user before `git push --force`, deleting
   user data, wiping files, or rewriting history.
3. **No unauthorized dependencies.** Use the standard library. Do not suggest or add
   third-party packages without user approval.
4. **Minimal diffs.** Do not reformat or refactor code outside the scope of the request.
5. **Do not invent project knowledge.** If an invariant, decision, or map entry does not clearly
   define a constraint or contract, stop and ask the user. Cite your source; say "I do not know"
   when you do not.

## 4. Before you finish

Run `python -m pytest -q tests`, `python scripts/verify_invariants.py`, and
`python scripts/check_dependency_budget.py`. Report failures verbatim.
