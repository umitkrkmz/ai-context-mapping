# Project Map

> Read this file before running exploratory `grep` or `find` commands.
> Every non-ignored file and directory has one row below; `tests/test_maps.py` fails when a row is missing or stale.
> Copy `scripts/` from the framework, then run `python scripts/init_mapping.py --merge` to add your project's files and describe each new row.

## File Index

One row per file or directory. Directories end with `/`; a `dir/**` row covers everything below it.

| Path | Category | Purpose | Invariants |
| ---- | -------- | ------- | ---------- |
| `AGENTS.md` | manifesto | Operating manifesto for AI agents: the five rules and Python conventions. | - |
| `maps/` | map | Repository navigation maps. | - |
| `maps/project-map.md` | map | Index of every path with category, purpose, and invariants. | - |
| `tests/` | test | Automated test suite. | - |
| `tests/test_maps.py` | test | Fails when a non-ignored path lacks a map row or CLAUDE.md drifts from AGENTS.md. | - |
