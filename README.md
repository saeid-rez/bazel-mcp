# Bazel MCP

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes Bazel build system capabilities to AI assistants.

Repo: [github.com/saeid-rez/bazel-mcp](https://github.com/saeid-rez/bazel-mcp)

## Tools

| Tool | Description |
|------|-------------|
| `bazel_query` | Run arbitrary `bazel query` expressions |
| `bazel_cquery` | Run configured `bazel cquery` expressions (select() and platforms) |
| `bazel_aquery` | Run action `bazel aquery` expressions (compiler flags, commands) |
| `list_targets` | List targets in a package or subtree |
| `get_deps` | Direct or transitive dependencies of a target |
| `get_rdeps` | Reverse dependencies within a scope |
| `show_target_info` | Rule definition via `query --output=build` |
| `find_affected_targets` | Find targets affected by changed files |
| `bazel_build` | Run `bazel build` with structured failure diagnostics |
| `bazel_test` | Run `bazel test` with structured target and failed-case results |
| `explain_build_file` | Read BUILD file contents for analysis |

## Usage

Requires [uv](https://docs.astral.sh/uv/). Configure the server with a Bazel workspace path if your MCP client does not start it from that workspace.

### Antigravity (agy)

Add the following to `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "bazel": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/saeid-rez/bazel-mcp",
        "bazel-mcp-server"
      ]
    }
  }
}
```

Bazel commands run in your active workspace by default. If Antigravity does not start the server from your Bazel workspace, pass `--workspace-root` explicitly:

```json
{
  "mcpServers": {
    "bazel": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/saeid-rez/bazel-mcp",
        "bazel-mcp-server",
        "--workspace-root",
        "/path/to/your/bazel/workspace"
      ]
    }
  }
}
```

### OpenCode

Add the following to `opencode.json` or `opencode.jsonc`. Replace `/path/to/your/bazel/workspace` with the absolute path to your Bazel workspace.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "bazel": {
      "type": "local",
      "command": [
        "uvx",
        "--from",
        "git+https://github.com/saeid-rez/bazel-mcp",
        "bazel-mcp-server",
        "--workspace-root",
        "/path/to/your/bazel/workspace"
      ],
      "enabled": true
    }
  }
}
```

### GitHub Copilot CLI

Add the following to `~/.copilot/mcp-servers.json`. Replace `/path/to/your/bazel/workspace` with the absolute path to your Bazel workspace.

```json
{
  "mcp": {
    "servers": {
      "bazel": {
        "command": "uvx",
        "args": [
          "--from",
          "git+https://github.com/saeid-rez/bazel-mcp",
          "bazel-mcp-server",
          "--workspace-root",
          "/path/to/your/bazel/workspace"
        ],
        "protocol": "stdio"
      }
    }
  }
}
```

Alternatively, run `/mcp add bazel` inside Copilot CLI and provide the same command and arguments.

### Install With uv

To install the server persistently instead of running it from GitHub, run:

```bash
uv tool install bazel-mcp-server
```

Then use the following installed-server configuration in place of the GitHub-based command above. Include `--workspace-root` and its path when the client does not start the server from the Bazel workspace.

Antigravity (agy):

```json
{
  "mcpServers": {
    "bazel": {
      "command": "bazel-mcp-server",
      "args": ["--workspace-root", "/path/to/your/bazel/workspace"]
    }
  }
}
```

OpenCode:

```json
{
  "mcp": {
    "bazel": {
      "type": "local",
      "command": ["bazel-mcp-server", "--workspace-root", "/path/to/your/bazel/workspace"],
      "enabled": true
    }
  }
}
```

GitHub Copilot CLI:

```json
{
  "mcp": {
    "servers": {
      "bazel": {
        "command": "bazel-mcp-server",
        "args": ["--workspace-root", "/path/to/your/bazel/workspace"],
        "protocol": "stdio"
      }
    }
  }
}
```

### Cursor

Add this to `.cursor/mcp.json` in the Bazel workspace.

```json
{
  "mcpServers": {
    "bazel": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/saeid-rez/bazel-mcp", "bazel-mcp-server"]
    }
  }
}
```

Bazel commands run in your open workspace by default.

If Cursor does not start the server from the Bazel workspace, pass the workspace explicitly:

```json
{
  "mcpServers": {
    "bazel": {
      "command": "uvx",
      "args": [
        "bazel-mcp-server",
        "--workspace-root",
        "/path/to/your/bazel/workspace"
      ]
    }
  }
}
```

Other optional flags:

```bash
bazel-mcp-server --bazel-path bazelisk --timeout 600 --max-output-chars 64000
```

## Development

Clone the repo and run tests locally:

```bash
git clone https://github.com/saeid-rez/bazel-mcp
cd bazel-mcp
uv sync --group dev
uv run pytest
```
