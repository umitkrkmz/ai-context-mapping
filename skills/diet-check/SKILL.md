---
description: Report how large this repository, its project map, and its agent instruction files are in estimated tokens, and flag oversized ones. Read-only.
---

Measure how much context this project costs. Do not change any file.

Use `python3` to run Python; if that command is missing or fails, use `python`. Run from
`${CLAUDE_PROJECT_DIR}`. Use the project's own `scripts/init_mapping.py` when it exists, otherwise
`${CLAUDE_PLUGIN_ROOT}/scripts/init_mapping.py`.

1. Run `init_mapping.py --stats`. It prints the repository and map size in estimated tokens (1 token is
   about 4 characters), the median and largest file, a modeled cost of map-guided reading, and the size
   of every agent instruction file. It needs `maps/project-map.md`; without one, offer
   `/ai-context-mapping:adopt`.
2. Summarize the numbers in a short table.
3. Say plainly that the guided-reading figure is a worst-case model, not a measured saving. In the
   framework's benchmarks, agents did not read whole repositories, and in the adopter setup the framework
   cost 38% more than a bare project (experiment 5 in docs/benchmark-results.md of the framework
   repository).
4. Point out anything that needs action:
   - The map is over 3,000 tokens: group more directories (`--collapse-threshold`) or shorten rows.
   - An instruction file (`AGENTS.md`, `CLAUDE.md`, Copilot or Cursor rules) is over 500 lines: move
     detail into `maps/`, `invariants/`, or `docs/`, and keep only the rules in the file.
5. If the user wants a fix, propose it and wait.
