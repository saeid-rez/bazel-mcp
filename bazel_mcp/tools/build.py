"""Bazel build and test MCP tools."""

from bazel_mcp.bazel import find_workspace_root, run_bazel
from bazel_mcp.build_parser import parse_bazel_build_output
from bazel_mcp.models import BazelBuildResult, BazelTestResult
from bazel_mcp.server import mcp
from bazel_mcp.test_parser import parse_bazel_test_output

_BUILD_TEST = {
    "readOnlyHint": False,
    "destructiveHint": False,
    "idempotentHint": False,
    "openWorldHint": True,
}


@mcp.tool(annotations=_BUILD_TEST)
async def bazel_build(
    targets: list[str],
    options: list[str] | None = None,
    timeout: int | None = None,
) -> BazelBuildResult:
    """Run a Bazel build and return structured diagnostics.

    options are passed as extra bazel flags (e.g. --config=ci, -c opt).
    """
    cmd = ["build", *targets]
    if options:
        cmd.extend(options)
    result = await run_bazel(cmd, timeout=timeout, check=False)
    return parse_bazel_build_output(
        result.stdout,
        result.stderr,
        result.return_code,
        duration=result.duration,
    )


@mcp.tool(annotations=_BUILD_TEST)
async def bazel_test(
    targets: list[str],
    options: list[str] | None = None,
    timeout: int | None = None,
) -> BazelTestResult:
    """Run Bazel tests and return structured pass/fail results with failure log excerpts."""
    cmd = ["test", *targets, "--test_output=errors"]
    if options:
        cmd.extend(options)
    result = await run_bazel(cmd, timeout=timeout, check=False)
    workspace = find_workspace_root()
    return parse_bazel_test_output(
        result.stdout,
        result.stderr,
        result.return_code,
        workspace=workspace,
    )
