"""Bazel build and test MCP tools."""

from bazel_mcp.bazel import find_workspace_root, run_bazel
from bazel_mcp.server import mcp

_BUILD_TEST = {
    "readOnlyHint": False,
}


@mcp.tool(annotations=_BUILD_TEST)
async def bazel_build(
    targets: list[str],
    options: list[str] | None = None,
    timeout: int | None = None,
) -> str:
    """Run a Bazel build and return stdout, stderr, and exit code.

    options are passed as extra bazel flags (e.g. --config=ci, -c opt).
    """
    cmd = ["build", *targets]
    if options:
        cmd.extend(options)
    result = await run_bazel(cmd, timeout=timeout, check=False)
    return (
        f"Exit code: {result.return_code}\n"
        f"Duration: {result.duration:.1f}s\n\n"
        f"--- stdout ---\n{result.stdout}\n"
        f"--- stderr ---\n{result.stderr}"
    )

