"""Tests for Bazel query tool command construction."""

from unittest.mock import AsyncMock, patch

import pytest

from bazel_mcp.bazel import BazelResult
from bazel_mcp.tools import query as query_tools


@pytest.mark.asyncio
async def test_get_deps_excludes_root_target():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="//pkg:dep\n", stderr="", return_code=0, duration=0.1)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.get_deps("//pkg:target", depth=1)

    assert result == "//pkg:dep\n"
    run_bazel.assert_awaited_once_with(
        ["query", "deps(//pkg:target, 1) except //pkg:target"]
    )


@pytest.mark.asyncio
async def test_get_rdeps_excludes_root_target():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="//app:bin\n", stderr="", return_code=0, duration=0.1)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.get_rdeps("//pkg:target", scope="//app/...")

    assert result == "//app:bin\n"
    run_bazel.assert_awaited_once_with(
        ["query", "rdeps(//app/..., //pkg:target) except //pkg:target"]
    )
