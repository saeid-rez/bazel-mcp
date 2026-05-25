"""FastMCP server instance and tool registration."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "bazel-mcp",
    instructions=(
        "MCP server for interacting with the Bazel build system. "
    ),
)

# Import tool modules so @mcp.tool decorators register handlers.
from bazel_mcp.tools import build, explain, query  # noqa: E402, F401
