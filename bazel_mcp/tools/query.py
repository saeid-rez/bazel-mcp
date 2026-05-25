"""Bazel query MCP tools."""

from bazel_mcp.bazel import run_bazel
from bazel_mcp.server import mcp

_READ_ONLY = {
    "readOnlyHint": True,
}


@mcp.tool(annotations=_READ_ONLY)
async def bazel_query(query: str, output_format: str = "label") -> str:
    """Run an arbitrary Bazel query expression.

    Query is read-only but can be expensive on broad patterns like //...
    output_format: label, build, xml, package, location, graph, etc.
    """
    result = await run_bazel(["query", f"--output={output_format}", query])
    return result.stdout

