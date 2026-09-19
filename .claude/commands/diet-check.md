---
description: Measure repository size and the estimated token savings of map-guided reading
allowed-tools: Bash(python scripts/init_mapping.py --stats*)
---

Measure how much context this repository costs and how much the project map saves.

1. Run `python scripts/init_mapping.py --stats`. It is read-only and prints:
   - the whole repository in estimated tokens (1 token is about 4 characters),
   - the size of `maps/project-map.md`,
   - the median and largest file,
   - the guided cost (map plus one median file, and map plus the largest file) as a percentage
     smaller than reading everything,
   - the line and token count of every agent instruction file.
2. Summarize the numbers in a short table.
3. Point out anything that needs action:
   - The map is over 3,000 tokens: group more directories (`--collapse-threshold`) or shorten
     row descriptions.
   - One file is over 25% of the repository: recommend splitting it.
   - An instruction file (`AGENTS.md`, `CLAUDE.md`, Copilot or Cursor rules) is over 500 lines:
     move detail into `maps/`, `invariants/`, or `docs/` and keep only the rules in the file.
     Very long instruction files bloat context and cause instructions to be missed.
4. Do not change any file. If the user wants a fix, propose it and wait.

For the model behind these numbers, see `docs/02-token-diet-calculator.md`.
