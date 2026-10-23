---
description: Install the ai-context-mapping guardrails in this project (AGENTS.md, CLAUDE.md, project map, invariants, tooling). Shows a plan first and never overwrites files.
argument-hint: "[--stack python|typescript|generic] [--agent cursor|copilot|codex] [--ci]"
disable-model-invocation: true
---

Install the ai-context-mapping framework into this project with `adopt.py`. The script copies files and
generates the project map. It never overwrites an existing file and runs nothing else.

Use `python3` to run Python; if that command is missing or fails, use `python`.

1. **Choose the stack.** If the arguments contain `--stack`, use it. Otherwise pick one and say why:
   `python` when the project has `pyproject.toml`, `requirements*.txt`, or mostly `.py` files;
   `typescript` when it has `package.json` or `tsconfig.json`; `generic` otherwise.
2. **Show the plan.** Run:

   ```bash
   python3 "${CLAUDE_PLUGIN_ROOT}/scripts/adopt.py" --target "${CLAUDE_PROJECT_DIR}" --agent claude --dry-run $ARGUMENTS
   ```

   Report which files it would add and which it would skip because they already exist.
3. **Ask before writing.** Wait for the user's yes, then run the same command without `--dry-run`.
4. **Describe the map.** Open `maps/project-map.md`. For every row whose purpose ends with
   `describe manually`, and every other generated purpose that is vague, read the file and write one
   accurate sentence. If you cannot tell what a file is for, ask the user. Never invent a purpose
   (AGENTS.md Rule 5).
5. **Review the invariants.** Explain that `invariants/negative-invariants.md` arrived with rules NI-001 to
   NI-009, which protect the copied tooling only. Ask the user which guards in their own code must never be
   removed, and add those as `NI-100` and up with the narrative template in that file. Do not invent
   invariants.
6. **Verify.** Run `/ai-context-mapping:verify-map` and `/ai-context-mapping:verify-invariants`.
7. **Next steps.** Relay the script's numbered next steps. `sh scripts/install_hooks.sh` writes a git
   hook, so ask before you run it. If a file was skipped (for example an existing `AGENTS.md`), offer to
   merge the framework's five rules into it, and show the diff before you change it.

The map gate (Rule 1 enforcement) stays off unless the user enables the plugin's `map_gate` option.
