"""FastMCP server instance and tool registration."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "bazel-mcp",
    instructions=(
        "MCP server for interacting with the Bazel build system. "
        "Use bazel_query for arbitrary query expressions (e.g. kind('cc_library', //...)). "
        "Use list_targets to list targets in a package pattern. "
        "Use get_deps/get_rdeps for dependency analysis. "
        "Use show_target_info for rule definitions (--output=build). "
        "Use bazel_build and bazel_test to run builds and tests. "
        "Use explain_build_file to read BUILD file contents for analysis. "
        "Large //... queries can be slow; prefer scoped package patterns when possible."
    ),
)

# Import tool modules so @mcp.tool decorators register handlers.
from bazel_mcp.tools import build, explain, query  # noqa: E402, F401
