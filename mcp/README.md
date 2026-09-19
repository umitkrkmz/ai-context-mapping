# Context MCP Server

A standalone [Model Context Protocol](https://modelcontextprotocol.io) server that gives AI
clients direct, cheap access to the project map. Instead of scanning the repository, the client
calls one tool and receives a curated index.

- **Zero dependencies.** One file, Python 3.9+ standard library only.
- **Transport.** JSON-RPC 2.0 over stdio, one JSON message per line.
- **Always fresh.** The map is re-read on every call; no restart after edits.

## Tools

| Tool                              | Returns                                                                         |
| --------------------------------- | ------------------------------------------------------------------------------- |
| `read_project_map()`              | The full content of `maps/project-map.md`.                                      |
| `get_file_purpose(file_path)`     | The category, purpose, and invariants (with their descriptions) for one path.   |

Example answer for `get_file_purpose("scripts/mutation_guard.py")`:

```text
Path: scripts/mutation_guard.py
Category: script
Purpose: Mutates a target function and verifies that its test fails.
Invariants:
  - NI-006: The mutation guard always restores the target file - ...
  - NI-007: The mutation guard disables bytecode caching - ...
Directory: scripts/ (script) - Command-line tooling and automation scripts.
```

Paths may use forward or back slashes, a leading `./`, or an absolute path inside the project.
Files covered by a `dir/**` group row resolve to that row. Unknown paths return an error with
close-match suggestions.

## Setup

Replace the paths below with the absolute path to your checkout. Use forward slashes or
escaped backslashes in JSON. Restart the client after editing its configuration.

### Claude Desktop

Edit `claude_desktop_config.json`:

- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`
- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
- Linux: `~/.config/Claude/claude_desktop_config.json`

macOS / Linux:

```json
{
  "mcpServers": {
    "project-context": {
      "command": "python3",
      "args": ["/absolute/path/to/your-project/mcp/context_server.py"],
      "env": {
        "AI_CONTEXT_ROOT": "/absolute/path/to/your-project"
      }
    }
  }
}
```

Windows:

```json
{
  "mcpServers": {
    "project-context": {
      "command": "python",
      "args": ["C:/path/to/your-project/mcp/context_server.py"],
      "env": {
        "AI_CONTEXT_ROOT": "C:/path/to/your-project"
      }
    }
  }
}
```

### Cursor

Create `.cursor/mcp.json` in the project (or `~/.cursor/mcp.json` for all projects):

```json
{
  "mcpServers": {
    "project-context": {
      "command": "python3",
      "args": ["${workspaceFolder}/mcp/context_server.py"],
      "env": {
        "AI_CONTEXT_ROOT": "${workspaceFolder}"
      }
    }
  }
}
```

### Claude Code

```bash
claude mcp add project-context -- python3 /absolute/path/to/your-project/mcp/context_server.py
```

### Serving several projects

Register one server entry per project, each with its own `AI_CONTEXT_ROOT`, or pass
`--root` in `args`. Without either, the server uses the parent of its own `mcp/` directory.

## Verify the installation

Validate the map without any client:

```bash
python mcp/context_server.py --check
```

Call a tool from the command line:

```bash
python mcp/context_server.py --call get_file_purpose --arg file_path=AGENTS.md
```

Speak the protocol by hand:

```bash
printf '%s\n' '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"manual","version":"0"}}}' '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | python mcp/context_server.py
```

Set `AI_CONTEXT_DEBUG=1` to log traffic to stderr (stdout carries protocol messages only).

## Protocol notes

- Implemented methods: `initialize`, `ping`, `tools/list`, `tools/call`, and all
  `notifications/*` (ignored). Other methods return JSON-RPC error `-32601`.
- Supported protocol versions: `2025-06-18`, `2025-03-26`, `2024-11-05`. The server echoes the
  client's version when supported and otherwise answers with the newest one.
- A tool that runs but cannot answer (for example an unknown path) returns a normal result with
  `isError: true`. Malformed arguments return JSON-RPC error `-32602`.

## Troubleshooting

| Symptom                              | Fix                                                                                   |
| ------------------------------------ | ------------------------------------------------------------------------------------- |
| Client shows the server as failed    | Run the `--check` command above; make sure `command` is a Python 3.9+ on your `PATH`. |
| "Project map not found"              | Create it: `python scripts/init_mapping.py`, or fix `AI_CONTEXT_ROOT`.                |
| "not listed in maps/project-map.md"  | The file is new: `python scripts/init_mapping.py --merge`, then describe the row.     |
| Windows path errors                  | Use forward slashes in JSON, or double every backslash.                               |
