"""FastMCP server instance and tool registration."""

from fastmcp import FastMCP

from bazel_mcp import __version__

mcp = FastMCP(
    "bazel-mcp",
    version=__version__,
    instructions=(
        "MCP server for interacting with the Bazel build system. "
        "Use bazel_query for arbitrary query expressions (e.g. kind('cc_library', //...)). "
        "Use bazel_cquery for configured query expressions (post-analysis, select() resolution, platforms). "
        "Use bazel_aquery for action graph inspection (compiler/linker commands, flags, inputs/outputs). "
        "Use list_targets to list targets in a package pattern. "
        "Use get_deps/get_rdeps for dependency analysis. "
        "Use show_target_info for rule definitions (--output=build). "
        "Use bazel_build and bazel_test to run builds and tests. "
        "Use explain_build_file to read BUILD file contents for analysis. "
        "Use find_affected_targets to find affected targets from git diff. "
        "Large //... queries can be slow; prefer scoped package patterns when possible."
    ),
)

# Import tool modules so @mcp.tool decorators register handlers.
from bazel_mcp.tools import build, explain, query  # noqa: E402, F401
