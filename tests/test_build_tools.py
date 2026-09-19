"""Tests for Bazel build MCP tools."""

from unittest.mock import AsyncMock, patch

import pytest

from bazel_mcp.bazel import BazelResult
from bazel_mcp.tools import build as build_tools


@pytest.mark.asyncio
async def test_bazel_build_returns_structured_diagnostics():
    run_bazel = AsyncMock(
        return_value=BazelResult(
            stdout="",
            stderr="/repo/src/App.swift:34:12: error: cannot find type 'Foo' in scope\n",
            return_code=1,
            duration=2.5,
        )
    )

    with patch.object(build_tools, "run_bazel", run_bazel):
        result = await build_tools.bazel_build(
            ["//app:app"],
            options=["--config=ci"],
            timeout=10,
        )

    run_bazel.assert_awaited_once_with(
        ["build", "//app:app", "--config=ci"],
        timeout=10,
        check=False,
    )
    assert result.success is False
    assert result.exit_code == 1
    assert result.duration_seconds == 2.5
    assert result.errors[0].file == "/repo/src/App.swift"
    assert result.errors[0].message == "cannot find type 'Foo' in scope"


@pytest.mark.asyncio
async def test_bazel_run_basic():
    run_bazel = AsyncMock(
        return_value=BazelResult(
            stdout="Tool output\n",
            stderr="",
            return_code=0,
            duration=1.2,
        )
    )

    with patch.object(build_tools, "run_bazel", run_bazel):
        result = await build_tools.bazel_run(
            target="//cmd:tool",
            args=["--flag", "val"],
        )

    run_bazel.assert_awaited_once_with(
        ["run", "//cmd:tool", "--", "--flag", "val"],
        timeout=60,
        check=False,
        cwd=None,
        env=None,
    )
    assert result.success is True
    assert result.exit_code == 0
    assert result.duration == 1.2
    assert result.stdout == "Tool output\n"
    assert result.stderr == ""


@pytest.mark.asyncio
async def test_bazel_run_with_options_and_env():
    run_bazel = AsyncMock(
        return_value=BazelResult(
            stdout="Done\n",
            stderr="",
            return_code=0,
            duration=0.5,
        )
    )

    with patch.object(build_tools, "run_bazel", run_bazel):
        result = await build_tools.bazel_run(
            target="//cmd:tool",
            options=["--config=ci", "-c", "opt"],
            env={"DEBUG": "1"},
            timeout=30,
        )

    run_bazel.assert_awaited_once_with(
        ["run", "--config=ci", "-c", "opt", "//cmd:tool"],
        timeout=30,
        check=False,
        cwd=None,
        env={"DEBUG": "1"},
    )
    assert result.success is True
    assert result.exit_code == 0


@pytest.mark.asyncio
async def test_bazel_run_with_valid_working_dir(tmp_path):
    sub = tmp_path / "sub"
    sub.mkdir()

    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="ok\n", stderr="", return_code=0, duration=0.8)
    )

    with patch.object(build_tools, "find_workspace_root", return_value=tmp_path):
        with patch.object(build_tools, "run_bazel", run_bazel):
            result = await build_tools.bazel_run(
                target="//cmd:tool",
                working_dir="sub",
            )

    run_bazel.assert_awaited_once_with(
        ["run", "//cmd:tool"],
        timeout=60,
        check=False,
        cwd=sub,
        env=None,
    )
    assert result.success is True


@pytest.mark.asyncio
async def test_bazel_run_invalid_working_dir(tmp_path):
    with patch.object(build_tools, "find_workspace_root", return_value=tmp_path):
        with pytest.raises(ValueError, match="outside the workspace root"):
            await build_tools.bazel_run(
                target="//cmd:tool",
                working_dir="../../outside",
            )


@pytest.mark.asyncio
async def test_bazel_run_failure_exit_code():
    run_bazel = AsyncMock(
        return_value=BazelResult(
            stdout="",
            stderr="Error: execution failed\n",
            return_code=1,
            duration=0.3,
        )
    )

    with patch.object(build_tools, "run_bazel", run_bazel):
        result = await build_tools.bazel_run(target="//cmd:tool")

    assert result.success is False
    assert result.exit_code == 1
    assert result.stderr == "Error: execution failed\n"


@pytest.mark.asyncio
async def test_bazel_run_invalid_target_label():
    with pytest.raises(ValueError, match="Invalid Bazel target label"):
        await build_tools.bazel_run(target="invalid-target")


def test_bazel_run_annotations():
    assert build_tools._BUILD_TEST["readOnlyHint"] is False
    assert build_tools._BUILD_TEST["openWorldHint"] is True
    assert build_tools._BUILD_TEST["idempotentHint"] is False


@pytest.mark.asyncio
async def test_bazel_run_timeout():
    from bazel_mcp.exceptions import BazelExecutionError

    run_bazel = AsyncMock(
        side_effect=BazelExecutionError(
            "Bazel command timed out after 60s: bazel run //cmd:tool",
            return_code=-1,
            stderr="",
        )
    )

    with patch.object(build_tools, "run_bazel", run_bazel):
        with pytest.raises(BazelExecutionError) as exc_info:
            await build_tools.bazel_run(target="//cmd:tool")

    assert exc_info.value.return_code == -1
    assert "timed out" in str(exc_info.value)
