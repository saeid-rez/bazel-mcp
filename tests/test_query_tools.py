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


# --- Tests for Story 1.1: bazel_cquery ---


@pytest.mark.asyncio
async def test_bazel_cquery_basic():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="//pkg:target (9f8b4a)\n", stderr="", return_code=0, duration=0.2)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.bazel_cquery("//pkg:target")

    assert result == "//pkg:target (9f8b4a)\n"
    run_bazel.assert_awaited_once_with(
        ["cquery", "--output=label", "//pkg:target"],
        max_chars=131072,
    )


@pytest.mark.asyncio
async def test_bazel_cquery_with_options_and_format():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="//pkg:target\n", stderr="", return_code=0, duration=0.3)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.bazel_cquery(
            "deps(//pkg:target)",
            output_format="textproto",
            options=["--config=ci", "--platforms=//platforms:linux"],
        )

    assert result == "//pkg:target\n"
    run_bazel.assert_awaited_once_with(
        ["cquery", "--output=textproto", "--config=ci", "--platforms=//platforms:linux", "deps(//pkg:target)"],
        max_chars=131072,
    )


@pytest.mark.asyncio
async def test_bazel_cquery_truncation():
    large_stdout = "".join(f"//pkg:target_{i} (cfg{i})\n" for i in range(100))
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout=large_stdout, stderr="", return_code=0, duration=0.2)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.bazel_cquery("//...", max_output_bytes=100)

    assert "Output truncated: exceeded max_output_bytes" in result
    assert "100" in result


@pytest.mark.asyncio
async def test_bazel_cquery_error():
    from bazel_mcp.exceptions import BazelExecutionError, BazelMcpError

    run_bazel = AsyncMock(
        side_effect=BazelExecutionError(
            "Bazel command failed (exit 7): bazel cquery bad",
            return_code=7,
            stderr="ERROR: syntax error at 'bad'",
        )
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        with pytest.raises(BazelMcpError) as exc_info:
            await query_tools.bazel_cquery("bad")

    assert exc_info.value.return_code == 7
    assert "syntax error" in str(exc_info.value)


# --- Tests for Story 1.2: bazel_aquery ---


@pytest.mark.asyncio
async def test_bazel_aquery_basic():
    aquery_output = "action 'CppCompile src/foo.o'\n  Mnemonic: CppCompile\n"
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout=aquery_output, stderr="", return_code=0, duration=0.4)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.bazel_aquery("mnemonic('CppCompile', //pkg:target)")

    assert result == aquery_output
    run_bazel.assert_awaited_once_with(
        ["aquery", "--output=text", "mnemonic('CppCompile', //pkg:target)"],
        max_chars=131072,
    )


@pytest.mark.asyncio
async def test_bazel_aquery_with_options_and_format():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="{\"artifacts\": []}\n", stderr="", return_code=0, duration=0.3)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.bazel_aquery(
            "//pkg:target",
            output_format="jsonproto",
            options=["--include_artifacts=false"],
        )

    assert result == "{\"artifacts\": []}\n"
    run_bazel.assert_awaited_once_with(
        ["aquery", "--output=jsonproto", "--include_artifacts=false", "//pkg:target"],
        max_chars=131072,
    )


@pytest.mark.asyncio
async def test_bazel_aquery_empty_actions():
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout="   \n  \n", stderr="", return_code=0, duration=0.1)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.bazel_aquery("mnemonic('NonExistent', //pkg:target)")

    assert result == "No matching actions found for query: mnemonic('NonExistent', //pkg:target)"


@pytest.mark.asyncio
async def test_bazel_aquery_truncation():
    large_stdout = "".join(f"action 'Action_{i}'\n  Command: gcc -c {i}.c\n" for i in range(50))
    run_bazel = AsyncMock(
        return_value=BazelResult(stdout=large_stdout, stderr="", return_code=0, duration=0.2)
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        result = await query_tools.bazel_aquery("//pkg:target", max_output_bytes=120)

    assert "Output truncated: exceeded max_output_bytes" in result
    assert "120" in result
    assert "action 'Action_0'" in result


@pytest.mark.asyncio
async def test_bazel_aquery_error():
    from bazel_mcp.exceptions import BazelExecutionError, BazelMcpError

    run_bazel = AsyncMock(
        side_effect=BazelExecutionError(
            "Bazel command failed (exit 2): bazel aquery bad_query",
            return_code=2,
            stderr="ERROR: invalid expression",
        )
    )

    with patch.object(query_tools, "run_bazel", run_bazel):
        with pytest.raises(BazelMcpError) as exc_info:
            await query_tools.bazel_aquery("bad_query")

    assert exc_info.value.return_code == 2
    assert "invalid expression" in str(exc_info.value)


def test_cquery_and_aquery_annotations():
    assert query_tools._READ_ONLY["readOnlyHint"] is True
    assert query_tools._READ_ONLY["idempotentHint"] is True
