# Site Map

The project map (`maps/project-map.md`) answers "what is this file?". This site map answers "how do I
get to it?": every command, tool, workflow, and reading path that leads into the repository.

## Reading order

| Audience           | Read in this order                                                                                          |
| ------------------ | ----------------------------------------------------------------------------------------------------------- |
| AI agent           | `AGENTS.md` -> `maps/project-map.md` -> invariants for the files you will touch -> `decisions/`             |
| New user           | `README.md` -> `docs/01-core-principles.md` -> `templates/<stack>/` -> `mcp/README.md`                      |
| Contributor        | `README.md` (Contributing) -> `invariants/negative-invariants.md` -> `docs/01-core-principles.md` section 9 |
| Skeptic            | `docs/02-token-diet-calculator.md` -> `docs/benchmark-results.md` -> `docs/case-study-mediagrab.md`         |

## CLI routes

| Command                                                         | Implemented in                     | Purpose                                            | Exit codes                          |
| --------------------------------------------------------------- | ---------------------------------- | -------------------------------------------------- | ----------------------------------- |
| `python scripts/init_mapping.py`                                | `scripts/init_mapping.py`          | Create `maps/project-map.md`                       | 0 ok, 1 exists, 2 bad root          |
| `python scripts/init_mapping.py --merge`                        | `scripts/init_mapping.py`          | Add new paths, keep descriptions, drop stale rows  | 0 ok                                |
| `python scripts/init_mapping.py --check`                        | `scripts/init_mapping.py`          | Read-only freshness check for CI                   | 0 current, 1 out of date            |
| `python scripts/init_mapping.py --stats`                        | `scripts/init_mapping.py`          | Token-diet report and instruction-file line counts | 0, 1 if the map is missing          |
| `python scripts/verify_invariants.py`                           | `scripts/verify_invariants.py`     | Enforce invariant rules and lint decisions         | 0 ok, 1 violations, 2 config error  |
| `python scripts/verify_invariants.py --list-rules`              | `scripts/verify_invariants.py`     | Show the loaded rules                              | 0                                   |
| `python scripts/check_dependency_budget.py`                     | `scripts/check_dependency_budget.py` | Enforce approved list and package ceiling        | 0 ok, 1 violation, 2 error          |
| `python scripts/mutation_guard.py --test T --target F.py:func`  | `scripts/mutation_guard.py`        | Prove a test fails when the function is broken     | 0 pass, 1 fail, 2 error             |
| `python scripts/mutation_guard.py --target F.py:func --test T --recover` | `scripts/mutation_guard.py` | Restore a file after an interrupted run          | 0                                   |
| `sh scripts/install_hooks.sh`                                   | `scripts/install_hooks.sh`         | Install the pre-commit hook                        | 0 ok, 1 error                       |
| `sh scripts/install_hooks.sh --uninstall`                       | `scripts/install_hooks.sh`         | Remove the managed hook                            | 0                                   |
| `python -m pytest -q tests`                                     | `tests/test_maps.py`               | Run the self-guarding tests                        | pytest codes                        |
| `python benchmarks/analyze_transcripts.py --dir D AGENT_ID` | `benchmarks/analyze_transcripts.py` | Tool calls, files read, tokens, and weighted cost from agent transcripts | 0 ok, 2 transcript not found |
| `python mcp/context_server.py --check`                          | `mcp/context_server.py`            | Validate the map without a client                  | 0 ok, 1 invalid                     |
| `python mcp/context_server.py --call TOOL --arg K=V`            | `mcp/context_server.py`            | Run one MCP tool from the shell                    | 0 ok, 1 tool error                  |

## Claude Code routes

Slash commands are Markdown files in `.claude/commands/`; hooks are configured in `.claude/settings.json`.

| Route                    | Runs                                                           | Purpose                                            |
| ------------------------ | -------------------------------------------------------------- | -------------------------------------------------- |
| `/verify-map`            | `init_mapping.py --check`, `pytest tests/test_maps.py`         | Confirm the map is complete; repair it if not      |
| `/verify-invariants`     | `verify_invariants.py [paths]`                                 | Enforce invariant rules; fix violations in code    |
| `/mutation-test`         | `mutation_guard.py --test T --target F.py:func`                | Prove a regression test can fail                   |
| `/diet-check`            | `init_mapping.py --stats`                                      | Report repository, map, and instruction-file size  |
| `PreToolUse` map gate    | `.claude/hooks/map_gate.py` (on Grep, Glob, Read, Bash, PowerShell, MCP tools) | Rule 1: block searches until the map is read; exit 2 |
| `PostToolUse` hook       | `.claude/hooks/guardrail_hook.py post-edit`                    | Check an edited `.py` file; exit 2 feeds back to Claude |
| `PreToolUse` hook (Bash) | `guardrail_hook.py is-git-commit`, then `check_dependency_budget.py` and `pytest tests/test_maps.py` | Commit gate; exit 2 blocks the commit |

Claude Code has no `PreCommit` event. The commit gate is a `PreToolUse` hook on `Bash` that acts
only when the command is a `git commit`. If `pytest` is missing it warns and continues, unless
`AI_GUARDRAILS_STRICT=1` is set.

## MCP routes

Transport: JSON-RPC 2.0 over stdio, served by `mcp/context_server.py`.

| Method / tool                    | Handler                          | Notes                                                           |
| -------------------------------- | -------------------------------- | --------------------------------------------------------------- |
| `initialize`                     | `handle_message`                 | Negotiates protocol version; declares the `tools` capability    |
| `ping`                           | `handle_message`                 | Returns `{}`                                                    |
| `tools/list`                     | `handle_message`                 | Lists the two tools below                                       |
| `tools/call` -> `read_project_map`  | `ContextTools.read_project_map`  | Full text of `maps/project-map.md`                              |
| `tools/call` -> `get_file_purpose`  | `ContextTools.get_file_purpose`  | Category, purpose, and resolved invariants for one path         |

## Automation routes

| Trigger                    | Runs                                                                        | Defined in                            |
| -------------------------- | --------------------------------------------------------------------------- | ------------------------------------- |
| `git commit`               | `verify_invariants.py`, `check_dependency_budget.py`, `tests/test_maps.py`  | hook written by `install_hooks.sh`    |
| Push to `main`, pull request | Map check, invariants, dependency budget, pytest, MCP handshake, mirror check | `.github/workflows/ai-guardrails.yml` |
| Agent session start        | Loads `AGENTS.md`, `CLAUDE.md`, Copilot and Cursor rules                    | `AGENTS.md`, `CLAUDE.md`, `.github/copilot-instructions.md`, `.cursor/rules/context-guardrails.mdc` |

## Environment variables

| Variable                | Read by                    | Effect                                                     |
| ----------------------- | -------------------------- | ---------------------------------------------------------- |
| `NO_COLOR`, `FORCE_COLOR` | all scripts               | Disable or force ANSI colors                               |
| `AI_CONTEXT_ROOT`       | `mcp/context_server.py`    | Project root to serve                                      |
| `AI_CONTEXT_DEBUG`      | `mcp/context_server.py`    | Log protocol traffic to stderr                             |
| `SKIP_AI_GUARDRAILS`    | installed pre-commit hook  | `1` skips the hook once                                    |
| `AI_GUARDRAILS_STRICT`  | git pre-commit hook, Claude Code commit gate | `1` makes a missing pytest a failure     |
| `AI_GUARDRAILS_PERMISSIVE` | `.claude/hooks/map_gate.py` | `1` disables the Rule 1 gate (manual or CI runs)            |
| `AI_GUARDRAILS_STATE_DIR`  | `.claude/hooks/map_gate.py` | Override the marker directory (default: system temp, per project) |
| `MUTATION_GUARD`        | set by `mutation_guard.py` | `1` inside test runs launched by the guard                 |
