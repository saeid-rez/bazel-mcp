"""Bazel build, test, and run MCP tools."""

from bazel_mcp.bazel import (
    find_workspace_root,
    run_bazel,
    validate_target_label,
    validate_working_dir,
)
from bazel_mcp.build_parser import parse_bazel_build_output
from bazel_mcp.models import BazelBuildResult, BazelRunResult, BazelTestResult
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


@mcp.tool(annotations=_BUILD_TEST)
async def bazel_run(
    target: str,
    args: list[str] | None = None,
    options: list[str] | None = None,
    env: dict[str, str] | None = None,
    working_dir: str | None = None,
    timeout: int = 60,
) -> BazelRunResult:
    """Execute a runnable Bazel target (bazel run) with custom arguments and environment variables.

    Args:
        target: Runnable Bazel target label (e.g. //cmd:tool).
        args: Command-line arguments passed to the executable after '--'.
        options: Optional Bazel flags passed before the target (e.g. ['-c', 'opt', '--config=ci']).
        env: Custom environment variables injected into the execution process.
        working_dir: Working directory for execution, validated to remain within the workspace boundary.
        timeout: Execution timeout in seconds (default 60).
    """
    validate_target_label(target)
    resolved_cwd = None
    if working_dir:
        workspace = find_workspace_root()
        resolved_cwd = validate_working_dir(working_dir, workspace)

    cmd = ["run"]
    if options:
        cmd.extend(options)
    cmd.append(target)
    if args:
        cmd.append("--")
        cmd.extend(args)

    result = await run_bazel(
        cmd,
        timeout=timeout,
        check=False,
        cwd=resolved_cwd,
        env=env,
    )
    return BazelRunResult(
        success=result.return_code == 0,
        exit_code=result.return_code,
        duration=result.duration,
        stdout=result.stdout,
        stderr=result.stderr,
    )
