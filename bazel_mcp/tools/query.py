"""Bazel query MCP tools."""

from bazel_mcp.bazel import normalize_query_pattern, run_bazel
from bazel_mcp.server import mcp

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


@mcp.tool(annotations=_READ_ONLY)
async def bazel_query(query: str, output_format: str = "label") -> str:
    """Run an arbitrary Bazel query expression.

    Query is read-only but can be expensive on broad patterns like //...
    output_format: label, build, xml, package, location, graph, etc.
    """
    result = await run_bazel(["query", f"--output={output_format}", query])
    return result.stdout


@mcp.tool(annotations=_READ_ONLY)
async def list_targets(package: str = "//...") -> str:
    """List all targets matching a package pattern.

    Default //... lists targets across the entire workspace (can be slow).
    For a single package use //pkg or pkg (normalized to //pkg:all).
    For a subtree use //pkg/...
    """
    pattern = normalize_query_pattern(package)
    result = await run_bazel(["query", pattern])
    return result.stdout

