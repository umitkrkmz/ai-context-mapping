---
description: Check that maps/project-map.md lists every file and has no placeholder descriptions, then repair a stale map. Use after adding, moving, or deleting files.
---

Verify the project map. The map is what agents read instead of searching, so a stale map misleads every
later session.

Use `python3` to run Python; if that command is missing or fails, use `python`. Run commands from
`${CLAUDE_PROJECT_DIR}`. Use the project's own `scripts/init_mapping.py` when it exists, otherwise
`${CLAUDE_PLUGIN_ROOT}/scripts/init_mapping.py`.

1. Run `init_mapping.py --check` and read its output.
2. If the project has `tests/test_maps.py`, run `python3 -m pytest -q tests/test_maps.py`. It also rejects
   placeholder descriptions. If pytest is not installed, say so; do not install it without the user's
   approval (AGENTS.md Rule 4).
3. Report both results verbatim: the exit status and any missing or stale paths.

If a check fails:

- Run `init_mapping.py --merge`. It adds rows for new paths, keeps existing descriptions, and drops rows
  for deleted paths.
- In `maps/project-map.md`, replace every generated description (they end with `describe manually`) with
  one accurate sentence. Read the file first; if you cannot tell what it is for, ask. If the file is
  protected by an invariant, put its ID in the `Invariants` column; otherwise write `-`.
- Run the checks again and confirm they pass.

Rules:

- Never weaken `tests/test_maps.py`, and never add a path to `.agentignore` just to make a check pass.
  Ignore only files that are generated, binary, or bulk data.
- Do not edit the `## File Index` heading or its column layout (invariant NI-009).
