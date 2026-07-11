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


@pytest.mark.asyncio
async def test_find_affected_targets_basic():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="//lib:lib\n//app:app\n", stderr="", return_code=0, duration=0.5)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.find_affected_targets(
            changed_files=["src/lib/BUILD", "src/lib/foo.go"],
            scope="//...",
        )

    assert result == "//lib:lib\n//app:app\n"
    run_bazel.assert_awaited_once_with(
        ["query", "rdeps(//..., set(//src/lib //src/lib:foo))"]
    )


@pytest.mark.asyncio
async def test_find_affected_targets_with_kind_filter():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="//lib:lib\n", stderr="", return_code=0, duration=0.3)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.find_affected_targets(
            changed_files=["src/lib/BUILD"],
            scope="//...",
            target_kind="cc_library",
        )

    assert result == "//lib:lib\n"
    run_bazel.assert_awaited_once_with(
        ["query", "kind('cc_library', rdeps(//..., set(//src/lib)))"]
    )


@pytest.mark.asyncio
async def test_find_affected_targets_empty():
    result = await query_tools.find_affected_targets(changed_files=[])
    assert result == "No files provided."


def test_file_to_bazel_label_build():
    assert query_tools._file_to_bazel_label("src/lib/BUILD") == "//src/lib"
    assert query_tools._file_to_bazel_label("src/lib/BUILD.bazel") == "//src/lib"


def test_file_to_bazel_label_source():
    assert query_tools._file_to_bazel_label("src/lib/foo.go") == "//src/lib:foo"
    assert query_tools._file_to_bazel_label("lib/bar.py") == "//lib:bar"


def test_file_to_bazel_label_bazel_ignored():
    assert query_tools._file_to_bazel_label("defs.bzl") is None
    assert query_tools._file_to_bazel_label("BUILD.bazel") == "//:"


@pytest.mark.asyncio
async def test_find_affected_targets_no_valid_targets():
    result = await query_tools.find_affected_targets(changed_files=[])
    assert result == "No files provided."
