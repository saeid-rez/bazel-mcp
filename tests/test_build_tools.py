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
