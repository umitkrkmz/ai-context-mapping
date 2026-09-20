# Project Map: ai-context-mapping

> Read this file before running exploratory `grep` or `find` commands.
> Every non-ignored file and directory has one row below. `tests/test_maps.py` fails when a row is missing or stale.
> After adding, moving, or deleting files run `python scripts/init_mapping.py --merge`, then describe the new rows.
> The `Invariants` column lists IDs defined in `invariants/negative-invariants.md` (`NI-*`) and `decisions/` (`ADR-*`). Read them before editing the file.

## Categories

| Category | Meaning |
| -------- | ------- |
| `manifesto` | Rules addressed to AI agents |
| `ignore` | Ignore lists |
| `map` | Navigation maps |
| `decision` | Machine-readable architecture decisions |
| `invariant` | Negative invariants |
| `persona` | Role-specific system prompts |
| `ci` | CI and automation pipelines |
| `docs` | Human documentation |
| `legal` | License |
| `test` | Automated tests |
| `script` | CLI tooling |
| `integration` | Servers and adapters for external tools |
| `template` | Boilerplate to copy into other projects |
| `config` | Configuration and settings files |

## File Index

One row per file or directory. Directories end with `/`; a `dir/**` row covers everything below it.

| Path | Category | Purpose | Invariants |
| ---- | -------- | ------- | ---------- |
| `.agentignore` | ignore | Paths agents must not read: build output, lockfiles, binaries, logs, bulk data, secrets. | - |
| `.claude/` | manifesto | Claude Code project configuration: slash commands, hooks, and settings. | - |
| `.claude/commands/` | manifesto | Project slash commands that run the guardrail scripts. | - |
| `.claude/commands/diet-check.md` | manifesto | /diet-check: report repository size, map size, and token savings via init_mapping --stats. | - |
| `.claude/commands/mutation-test.md` | manifesto | /mutation-test: prove a regression test fails when its function is broken; parameter guidance. | - |
| `.claude/commands/verify-invariants.md` | manifesto | /verify-invariants: run the AST invariant checker and fix violations without deleting rules. | - |
| `.claude/commands/verify-map.md` | manifesto | /verify-map: run init_mapping --check and the map tests, then repair a stale map. | - |
| `.claude/hooks/` | script | Claude Code hook scripts. | - |
| `.claude/hooks/guardrail_hook.py` | script | Hook adapter: runs verify_invariants on edited .py files (exit 2 on violation); detects git commits. | NI-001, NI-002, NI-005 |
| `.claude/hooks/map_gate.py` | script | PreToolUse gate enforcing Rule 1: blocks Grep, Glob, and exploratory shell search until the map is read. Also holds the opt-in ablation mode `AI_GUARDRAILS_BLOCK_SEARCH_ONLY=1` (blocks broad searches, needs no map). | NI-001, NI-005, NI-010 |
| `.claude/settings.json` | config | Claude Code hooks: map gate (Rule 1), invariant check after edits, and a commit gate (budget, map test). | - |
| `.cursor/` | manifesto | Cursor editor configuration. | - |
| `.cursor/rules/` | manifesto | Cursor rule files. | - |
| `.cursor/rules/context-guardrails.mdc` | manifesto | Always-on Cursor rule: use the map, respect invariants, ask before destructive actions. | - |
| `.gitattributes` | config | Forces LF line endings for scripts and the AGENTS.md/CLAUDE.md pair on every OS. | - |
| `.github/` | ci | GitHub-specific configuration. | - |
| `.github/copilot-instructions.md` | manifesto | Copilot instructions: map first, invariants, the five rules. | - |
| `.github/workflows/` | ci | GitHub Actions workflows. | - |
| `.github/workflows/ai-guardrails.yml` | ci | CI: map freshness, invariants, dependency budget, tests, MCP handshake, CLAUDE.md mirror. | - |
| `.gitignore` | ignore | Files Git must not track: caches, virtual environments, mutation leftovers, local settings. | - |
| `AGENTS.md` | manifesto | Primary operating manifesto for AI agents: the five rules, commands, definition of done. | NI-008 |
| `CLAUDE.md` | manifesto | Byte-identical mirror of AGENTS.md for Claude Code. | NI-008 |
| `LICENSE` | legal | MIT license. | - |
| `README.md` | docs | Landing page: diagrams, 3-minute quickstart, feature matrix, tools, contributing. | - |
| `benchmarks/` | test | Benchmark material for docs/benchmark-results.md: two fixtures and `results/` (manifest.json and results.json; all agent-ignored), framework layers, scoring, analysis. | - |
| `benchmarks/acceptance_check.py` | test | Hidden scoring check: exactly 50.00 must ship free. Not named test_*.py, so pytest skips it. | - |
| `benchmarks/analyze_transcripts.py` | test | Derives tool calls, files read, tokens by type, weighted cost, and the model ID from Claude Code agent transcripts; exports benchmarks/results/results.json and renders or checks the tables in docs/benchmark-results.md. | - |
| `benchmarks/conftest.py` | test | Tells pytest to skip the benchmark fixtures when run from the repository root. | - |
| `benchmarks/shipdesk-large-overlay/**` | test | Framework layer for the large benchmark: AGENTS.md, CLAUDE.md, a 147-row map, and four invariants. | - |
| `benchmarks/shipdesk-overlay/**` | test | Framework layer for benchmark Agent B: AGENTS.md, CLAUDE.md, a hand-written map, and two invariants. | - |
| `decisions/` | decision | Machine-readable architecture decision records. | ADR-0001 |
| `decisions/0001-no-database-file-store.yaml` | decision | ADR-0001: state lives in plain files; forbids databases, ORMs, and services. | ADR-0001 |
| `decisions/README.md` | decision | Schema, YAML subset, and usage rules for decision records. | - |
| `docs/` | docs | Long-form documentation. | - |
| `docs/01-core-principles.md` | docs | Rationale: token diet, file-based stores, and the guardrail layers. | - |
| `docs/02-token-diet-calculator.md` | docs | Token and cost model: whole-repo scanning vs map-guided reads, with a measuring script. | - |
| `docs/benchmark-results.md` | docs | Two A/B experiments (4.4k and 55.6k-token projects): no measured token savings; correctness parity; limits. | - |
| `docs/case-study-mediagrab.md` | docs | Case study of the MediaGrab architecture: zero DB, 100+ tests, map-guided AI work. | - |
| `invariants/` | invariant | Negative invariants. | - |
| `invariants/negative-invariants.md` | invariant | Defines negative invariants, templates, and the live machine-checked NI-* rules. | NI-001, NI-002, NI-003, NI-004, NI-005, NI-006, NI-007, NI-009 |
| `maps/` | map | Repository navigation maps. | - |
| `maps/project-map.md` | map | This file: the index of every path with category, purpose, and invariants. | NI-009 |
| `maps/site-map.md` | map | Route table for CLI commands, MCP tools, CI jobs, hooks, and the reading order. | - |
| `mcp/` | integration | Model Context Protocol server and its setup guide. | - |
| `mcp/README.md` | integration | Setup for Claude Desktop, Cursor, and Claude Code with copy-paste config. | - |
| `mcp/context_server.py` | integration | Stdio JSON-RPC MCP server exposing read_project_map and get_file_purpose. | NI-001, NI-002, NI-003, NI-005, NI-009 |
| `personas/` | persona | Role-specific system prompts for AI workflows. | - |
| `personas/refactorer.md` | persona | Refactorer persona: change structure, never behavior, respect invariants. | - |
| `personas/tester.md` | persona | Tester persona: regression test first, mutation-verified. | - |
| `personas/ux_architect.md` | persona | UX architect persona: flows, error copy, accessibility, contract safety. | - |
| `scripts/` | script | Standard-library-only guardrail tooling. | NI-001 |
| `scripts/check_dependency_budget.py` | script | Audits requirements, package.json, and pyproject against an allow-list and ceiling; exits 1. | NI-001, NI-004, NI-005 |
| `scripts/init_mapping.py` | script | Scans the tree; generates or merges maps/project-map.md; --check freshness and --stats token report. | NI-001, NI-004, NI-005, NI-009 |
| `scripts/install_hooks.sh` | script | Installs the git pre-commit hook that runs the guardrail checks. | - |
| `scripts/mutation_guard.py` | script | Mutates a target function (incl. boundary shifts) and verifies its test fails; restores the file. | NI-001, NI-002, NI-004, NI-005, NI-006, NI-007 |
| `scripts/verify_invariants.py` | script | AST checker for forbidden imports, isolated wrappers, forbidden calls, and required guards. | NI-001, NI-004, NI-005 |
| `templates/` | template | Boilerplate to copy into other projects. | - |
| `templates/generic/` | template | Language-agnostic starter. | - |
| `templates/generic/AGENTS.md` | template | Language-agnostic AGENTS.md: the five rules and the guardrail commands. | - |
| `templates/generic/maps/` | template | Map directory for the generic starter. | - |
| `templates/generic/maps/project-map.md` | template | Minimal project map for the generic starter. | - |
| `templates/python/` | template | Python and pytest starter. | - |
| `templates/python/AGENTS.md` | template | AGENTS.md tuned for Python projects using pytest. | - |
| `templates/python/maps/` | template | Map directory for the Python starter. | - |
| `templates/python/maps/project-map.md` | template | Minimal project map for the Python starter. | - |
| `templates/python/tests/` | template | Tests directory for the Python starter. | - |
| `templates/python/tests/test_maps.py` | template | Copy of tests/test_maps.py: fails when a file is missing from the map. | - |
| `templates/typescript/` | template | TypeScript starter for vitest or jest. | - |
| `templates/typescript/AGENTS.md` | template | AGENTS.md tuned for TypeScript projects using vitest or jest. | - |
| `templates/typescript/maps/` | template | Map directory for the TypeScript starter. | - |
| `templates/typescript/maps/project-map.md` | template | Minimal project map for the TypeScript starter. | - |
| `templates/typescript/tests/` | template | Tests directory for the TypeScript starter. | - |
| `templates/typescript/tests/test_maps.test.ts` | template | TypeScript port of the map coverage test for vitest or jest. | - |
| `tests/` | test | Self-guarding test suite. | - |
| `tests/__init__.py` | test | Marks tests as a package so pytest module names cannot collide with templates. | - |
| `tests/test_hooks.py` | test | Tests the map gate with mock tool-use payloads (block, unlock, allow, scope, bypass), the search-suppression ablation mode, and the settings wiring. | NI-010 |
| `tests/test_benchmarks.py` | test | Tests the reporting pipeline with synthetic transcripts and checks that results.json and the tables in docs/benchmark-results.md agree. | - |
| `tests/test_maps.py` | test | Fails when any non-ignored path lacks a map row, or CLAUDE.md drifts from AGENTS.md. | NI-008, NI-009 |

## Route Table

| Kind | Route | Handler | File |
| ---- | ----- | ------- | ---- |
| CLI | `python .claude/hooks/guardrail_hook.py` | `main()` | `.claude/hooks/guardrail_hook.py` |
| CLI | `python .claude/hooks/map_gate.py` | `main()` | `.claude/hooks/map_gate.py` |
| CLI | `python benchmarks/analyze_transcripts.py` | `main()` | `benchmarks/analyze_transcripts.py` |
| CLI | `python mcp/context_server.py` | `main()` | `mcp/context_server.py` |
| CLI | `python scripts/check_dependency_budget.py` | `main()` | `scripts/check_dependency_budget.py` |
| CLI | `python scripts/init_mapping.py` | `main()` | `scripts/init_mapping.py` |
| CLI | `python scripts/mutation_guard.py` | `main()` | `scripts/mutation_guard.py` |
| CLI | `python scripts/verify_invariants.py` | `main()` | `scripts/verify_invariants.py` |
