# Negative Invariants

A **negative invariant** is a statement about what must **not** change. It protects code,
structure, or behavior that looks redundant, ugly, or over-engineered but exists because
something once broke.

AI agents are trained to simplify. Left alone, they will happily delete a "pointless" retry,
inline a "needless" wrapper, or replace a strange guard with the obvious idiom. Negative
invariants tell them, in a form they can read and a machine can check, where that instinct
is wrong.

## Positive vs. negative invariants

| Kind     | Says                                   | Example                                             |
| -------- | -------------------------------------- | --------------------------------------------------- |
| Positive | "The system must always do X."         | "Every response includes a request ID."             |
| Negative | "Nobody may remove, bypass, or add Y." | "Never delete the empty-payload guard in `parse()`." |

Positive invariants are usually covered by ordinary tests. Negative invariants are not:
a test cannot easily notice that a guard is *gone* unless someone wrote a test for that exact
edge case. That gap is what this file closes.

## The two layers

1. **Machine-checked rules** are `invariant-rule` blocks (JSON). `scripts/verify_invariants.py`
   enforces them on every commit and in CI.
2. **Narrative invariants** are prose entries that agents and reviewers must respect. Add an
   `INVARIANT(NI-xxx)` marker comment next to the protected code and, where possible, a
   `required-text` rule so its removal is detected.

Every invariant has a stable ID (`NI-001`, `NI-002`, ...). IDs are referenced from the
`Invariants` column of `maps/project-map.md`, so an agent that opens a file learns which
invariants apply before it edits.

## Rule types

| Type               | Use it to                                                    | Key fields                           |
| ------------------ | ------------------------------------------------------------ | ------------------------------------ |
| `forbidden-import` | Block a layer from importing another layer or a package      | `forbidden`, `scope`, `allow_in`     |
| `isolated-import`  | Force all use of a module through one wrapper file           | `modules`, `allowed_in`, `use`       |
| `stdlib-only`      | Keep a directory free of third-party imports                 | `allow`, `scope`                     |
| `forbidden-call`   | Ban dangerous calls (`eval`, `os.system`), even via aliases  | `calls`, `scope`, `allow_in`         |
| `required-text`    | Fail when a protected guard or marker is deleted             | `file`, `contains`                   |

Common fields: `id`, `type`, `description`, `scope` (globs, default `**/*.py`), `exclude`.
The checker resolves relative imports, import aliases, and constant-string
`__import__()` / `importlib.import_module()` calls, so the usual bypasses are caught.

## Template: machine-checked rule

Copy this block, change the values, and keep the fence info string exactly `invariant-rule`.

````markdown
```invariant-rule
{
  "id": "NI-0xx",
  "type": "isolated-import",
  "description": "Only http_client.py may import 'requests'; everything else uses its wrapper.",
  "modules": ["requests"],
  "allowed_in": ["src/net/http_client.py"],
  "use": "src/net/http_client.py",
  "scope": ["src/**/*.py"]
}
```
````

## Template: narrative invariant

```markdown
### NI-1xx: <short imperative title>

- **Protects:** <file, function, or behavior>
- **Looks like:** <why it appears redundant or removable>
- **Exists because:** <the incident, bug, or platform quirk that created it>
- **Never:** <the specific edits that are forbidden>
- **Safe alternatives:** <what an agent may do instead>
- **Enforced by:** <rule ID, test name, or "review only">
- **Added:** <date or commit>
```

## Examples (from a hypothetical downloader)

These are illustrations of the format, not rules of this repository.

### NI-101: Keep the Windows long-path prefix in `safe_path()`

- **Protects:** `safe_path()` in `storage/paths.py`
- **Looks like:** A no-op string concatenation on non-Windows platforms.
- **Exists because:** Paths over 260 characters silently failed on Windows and lost the
  user's downloaded files.
- **Never:** Inline `safe_path()`, drop the `\\?\` prefix, or replace it with `Path.resolve()`.
- **Safe alternatives:** Extend it with new normalization steps and add a test per step.
- **Enforced by:** `required-text` rule plus `tests/test_paths.py::test_long_path_is_prefixed`.

### NI-102: Retry-After handling must not be "simplified" to fixed backoff

- **Protects:** the `429` branch in `net/fetch.py`
- **Looks like:** Duplicate logic next to the generic exponential backoff.
- **Exists because:** A provider bans clients that ignore `Retry-After`.
- **Never:** Merge the two branches or remove the header parsing.
- **Enforced by:** `INVARIANT(NI-102)` marker and a regression test.

### NI-103: All JSON persistence goes through `store.atomic_write()`

- **Protects:** the file-based data store (see `decisions/0001-no-database-file-store.yaml`).
- **Never:** Call `open(path, "w")` or `Path.write_text()` on store files directly.
- **Enforced by:** an `isolated-import` or `forbidden-call` rule scoped to `src/**`.

## Rules for this repository

The blocks below are live: `python scripts/verify_invariants.py` enforces them.

### NI-001: The tooling uses only the standard library

`scripts/`, `mcp/`, and `.claude/hooks/` must run on a clean Python 3.9+ install with no `pip install`. That is
the whole promise of the framework: guardrails must never become a supply-chain risk.

```invariant-rule
{
  "id": "NI-001",
  "type": "stdlib-only",
  "description": "Scripts, the MCP server, and Claude Code hooks may import only the Python standard library.",
  "scope": ["scripts/**/*.py", "mcp/**/*.py", ".claude/**/*.py"]
}
```

### NI-002: `subprocess` is isolated in the mutation guard

Only `scripts/mutation_guard.py` needs to launch a test runner. Every other file must stay
free of process spawning so that it cannot be turned into a command-injection vector.

```invariant-rule
{
  "id": "NI-002",
  "type": "isolated-import",
  "description": "Only scripts/mutation_guard.py may import subprocess.",
  "modules": ["subprocess"],
  "allowed_in": ["scripts/mutation_guard.py"],
  "use": "scripts/mutation_guard.py",
  "scope": ["**/*.py"],
  "exclude": ["templates/**"]
}
```

### NI-003: The MCP server stays standalone

`mcp/context_server.py` is copied into other projects on its own. It must not import
anything from `scripts/`.

```invariant-rule
{
  "id": "NI-003",
  "type": "forbidden-import",
  "description": "mcp/ must not import from the scripts layer.",
  "forbidden": ["scripts", "init_mapping", "verify_invariants", "check_dependency_budget", "mutation_guard"],
  "scope": ["mcp/**/*.py"]
}
```

### NI-004: Scripts never depend on the MCP server

Each script is a standalone CLI. Sharing code through the MCP server would create a hidden
coupling in the opposite direction.

```invariant-rule
{
  "id": "NI-004",
  "type": "forbidden-import",
  "description": "scripts/ must not import from the mcp layer.",
  "forbidden": ["mcp", "context_server"],
  "scope": ["scripts/**/*.py"]
}
```

### NI-005: No dynamic code execution or shell-out shortcuts

`eval`, `exec`, `os.system`, `os.popen`, and `shutil.rmtree` are banned in the tooling.
Arguments passed to child processes must be argument lists, never shell strings, and the
tools never delete directory trees (AGENTS.md Rule 3).

```invariant-rule
{
  "id": "NI-005",
  "type": "forbidden-call",
  "description": "eval, exec, os.system, os.popen, and shutil.rmtree are forbidden in scripts/, mcp/, and .claude/.",
  "calls": ["eval", "exec", "os.system", "os.popen", "shutil.rmtree"],
  "scope": ["scripts/**/*.py", "mcp/**/*.py", ".claude/**/*.py"]
}
```

### NI-006: The mutation guard always restores the target file

`scripts/mutation_guard.py` rewrites a user's source file in place. The restore step must
run in a `finally` block, on `SIGINT`/`SIGTERM`, and via the on-disk backup. Removing any of
them risks leaving a user's code silently mutated.

```invariant-rule
{
  "id": "NI-006",
  "type": "required-text",
  "description": "The mutation guard must keep its restore-in-finally, signal, and backup safeguards.",
  "file": "scripts/mutation_guard.py",
  "contains": ["INVARIANT(NI-006): restore", "INVARIANT(NI-006): signals", "INVARIANT(NI-006): backup"]
}
```

### NI-007: The mutation guard disables bytecode caching

A mutation such as `==` to `!=` keeps the file size identical. Python's `.pyc` staleness
check uses mtime and size, so without `PYTHONDONTWRITEBYTECODE` a mutant could run cached
bytecode of the original and be judged for the wrong reason.

```invariant-rule
{
  "id": "NI-007",
  "type": "required-text",
  "description": "The mutation guard must keep bytecode caching disabled for mutant runs.",
  "file": "scripts/mutation_guard.py",
  "contains": ["INVARIANT(NI-007)", "PYTHONDONTWRITEBYTECODE"]
}
```

### NI-008: `CLAUDE.md` mirrors `AGENTS.md`

Claude Code reads `CLAUDE.md`; every other agent reads `AGENTS.md`. They must never diverge.
Edit `AGENTS.md`, then copy it over `CLAUDE.md`. `tests/test_maps.py` enforces this.

### NI-009: The map keeps its `File Index` section

`tests/test_maps.py`, `scripts/init_mapping.py`, and `mcp/context_server.py` all parse the
table under the `## File Index` heading. Renaming the heading or changing the four column
order (`Path`, `Category`, `Purpose`, `Invariants`) silently disables the guardrails.

```invariant-rule
{
  "id": "NI-009",
  "type": "required-text",
  "description": "maps/project-map.md must keep the File Index heading and column layout.",
  "file": "maps/project-map.md",
  "contains": ["## File Index", "| Path | Category | Purpose | Invariants |"]
}
```

## How to add an invariant

1. Pick the next free ID and write the narrative entry.
2. Add a machine-checked rule if the constraint can be expressed with the types above.
3. Add an `INVARIANT(NI-xxx)` comment beside the protected code.
4. Reference the ID in the file's `Invariants` column in `maps/project-map.md`.
5. Run `python scripts/verify_invariants.py --list-rules` to confirm the rule loads.

## How to change or retire an invariant

Invariants are removed only with explicit user approval. State in the commit message which
incident no longer applies, then delete the rule, the marker, and the map references in the
same commit.
