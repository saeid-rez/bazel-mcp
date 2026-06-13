# Bazel MCP

A [Model Context Protocol](https://modelcontextprotocol.io/) server that exposes Bazel build system capabilities to AI assistants.

Repo: [github.com/saeid-rez/bazel-mcp](https://github.com/saeid-rez/bazel-mcp)

## Tools

| Tool | Description |
|------|-------------|
| `bazel_query` | Run arbitrary `bazel query` expressions |
| `list_targets` | List targets in a package or subtree |
| `get_deps` | Direct or transitive dependencies of a target |
| `get_rdeps` | Reverse dependencies within a scope |
| `show_target_info` | Rule definition via `query --output=build` |
| `bazel_build` | Run `bazel build` |
| `bazel_test` | Run `bazel test` with structured results |
| `explain_build_file` | Read BUILD file contents for analysis |

## Usage

Run against a Bazel workspace. Open that repo in Cursor, then add to `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "bazel": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/saeid-rez/bazel-mcp", "bazel-mcp"]
    }
  }
}
```

Requires [uv](https://docs.astral.sh/uv/). Bazel commands run in your open workspace by default.

If your MCP client does not start the server from the Bazel workspace, pass the workspace explicitly:

```json
{
  "mcpServers": {
    "bazel": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/saeid-rez/bazel-mcp",
        "bazel-mcp",
        "--workspace-root",
        "/path/to/your/bazel/workspace"
      ]
    }
  }
}
```

Other optional flags:

```bash
bazel-mcp --bazel-path bazelisk --timeout 600 --max-output-chars 64000
```

## Development

Clone the repo and run tests locally:

```bash
git clone https://github.com/saeid-rez/bazel-mcp
cd bazel-mcp
uv sync --group dev
uv run pytest
```
