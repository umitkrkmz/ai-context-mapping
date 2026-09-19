---
description: Verify that maps/project-map.md lists every file and that the map tests pass
allowed-tools: Bash(python scripts/init_mapping.py --check*), Bash(python -m pytest -q tests/test_maps.py*)
---

Verify the project map. The map is what agents read instead of searching, so a stale map
misleads every later session.

1. Run `python scripts/init_mapping.py --check` and read its output.
2. Run `python -m pytest -q tests/test_maps.py` and read its output.
3. Report both results verbatim: exit status, and the list of missing or stale paths if any.

If either check fails:

- Run `python scripts/init_mapping.py --merge`. It adds rows for new paths, keeps existing
  descriptions, and drops rows for deleted paths.
- Open `maps/project-map.md` and replace every auto-generated description (they end with
  "describe manually") with one accurate sentence. If the file is protected by an invariant,
  put its ID in the `Invariants` column; otherwise write `-`.
- Run both checks again and confirm they pass.

Rules:

- Never weaken `tests/test_maps.py`, and never add a path to `.agentignore` just to make the
  check pass. Ignore only files that are generated, binary, or bulk data.
- Do not edit the `## File Index` heading or its column layout (invariant NI-009).
- If `pytest` is not installed, say so; do not install it without the user's approval
  (AGENTS.md Rule 4).
