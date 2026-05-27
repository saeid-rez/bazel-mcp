"""Tests for bazel.py helpers and run_bazel."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from bazel_mcp.bazel import (
    find_workspace_root,
    normalize_query_pattern,
    run_bazel,
    truncate_output,
    validate_target_label,
)
from bazel_mcp.exceptions import BazelExecutionError, WorkspaceNotFoundError
from bazel_mcp.settings import get_settings


@pytest.fixture(autouse=True)
def clear_settings_cache():
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class TestNormalizeQueryPattern:
    def test_workspace_default(self):
        assert normalize_query_pattern("//...") == "//..."

    def test_single_package(self):
        assert normalize_query_pattern("foo/bar") == "//foo/bar:all"
        assert normalize_query_pattern("//foo/bar") == "//foo/bar:all"

    def test_subtree(self):
        assert normalize_query_pattern("//foo/...") == "//foo/..."

    def test_target_passthrough(self):
        assert normalize_query_pattern("//foo:bar") == "//foo:bar"


class TestValidateTargetLabel:
    def test_valid(self):
        validate_target_label("//pkg:target")
        validate_target_label("//:target")
        validate_target_label("@repo//pkg:target")
        validate_target_label("//pkg:target+with=chars,~ok")

    def test_invalid(self):
        with pytest.raises(ValueError, match="Invalid Bazel target"):
            validate_target_label("not-a-label")


class TestTruncateOutput:
    def test_no_truncation(self):
        assert truncate_output("short", 100) == "short"

    def test_truncates_long(self):
        text = "a" * 100
        result = truncate_output(text, 40)
        assert "truncated" in result
        assert len(result) < 100


class TestFindWorkspaceRoot:
    def test_finds_module_bazel(self, tmp_path: Path, monkeypatch):
        (tmp_path / "MODULE.bazel").write_text('module(name = "test")\n')
        sub = tmp_path / "pkg"
        sub.mkdir()
        monkeypatch.chdir(sub)
        monkeypatch.delenv("BAZEL_MCP_WORKSPACE_ROOT", raising=False)
        assert find_workspace_root() == tmp_path.resolve()

    def test_explicit_workspace_root(self, tmp_path: Path, monkeypatch):
        (tmp_path / "MODULE.bazel").write_text('module(name = "test")\n')
        monkeypatch.setenv("BAZEL_MCP_WORKSPACE_ROOT", str(tmp_path))
        assert find_workspace_root() == tmp_path.resolve()

    def test_missing_workspace(self, tmp_path: Path, monkeypatch):
        monkeypatch.chdir(tmp_path)
        monkeypatch.delenv("BAZEL_MCP_WORKSPACE_ROOT", raising=False)
        with pytest.raises(WorkspaceNotFoundError):
            find_workspace_root()


@pytest.mark.asyncio
class TestRunBazel:
    async def test_success(self, tmp_path: Path, monkeypatch):
        (tmp_path / "MODULE.bazel").write_text('module(name = "test")\n')
        monkeypatch.setenv("BAZEL_MCP_WORKSPACE_ROOT", str(tmp_path))

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"ok\n", b""))
        mock_proc.returncode = 0

        with patch("bazel_mcp.bazel.resolve_bazel_binary", return_value="bazel"):
            with patch(
                "asyncio.create_subprocess_exec",
                return_value=mock_proc,
            ) as mock_exec:
                result = await run_bazel(["query", "//..."])

        assert result.stdout == "ok\n"
        assert result.return_code == 0
        mock_exec.assert_called_once()
        assert mock_exec.call_args[0][0] == "bazel"
        assert mock_exec.call_args.kwargs["cwd"] == tmp_path.resolve()

    async def test_check_false_on_failure(self, tmp_path: Path, monkeypatch):
        (tmp_path / "MODULE.bazel").write_text('module(name = "test")\n')
        monkeypatch.setenv("BAZEL_MCP_WORKSPACE_ROOT", str(tmp_path))

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"error\n"))
        mock_proc.returncode = 1

        with patch("bazel_mcp.bazel.resolve_bazel_binary", return_value="bazel"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                result = await run_bazel(["build", "//foo"], check=False)

        assert result.return_code == 1
        assert "error" in result.stderr

    async def test_raises_on_failure_when_check_true(self, tmp_path: Path, monkeypatch):
        (tmp_path / "MODULE.bazel").write_text('module(name = "test")\n')
        monkeypatch.setenv("BAZEL_MCP_WORKSPACE_ROOT", str(tmp_path))

        mock_proc = AsyncMock()
        mock_proc.communicate = AsyncMock(return_value=(b"", b"fail\n"))
        mock_proc.returncode = 1

        with patch("bazel_mcp.bazel.resolve_bazel_binary", return_value="bazel"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                with pytest.raises(BazelExecutionError) as exc_info:
                    await run_bazel(["query", "bad"])

        assert exc_info.value.return_code == 1

    async def test_timeout_kills_and_drains_process(self, tmp_path: Path, monkeypatch):
        (tmp_path / "MODULE.bazel").write_text('module(name = "test")\n')
        monkeypatch.setenv("BAZEL_MCP_WORKSPACE_ROOT", str(tmp_path))

        call_count = 0

        async def communicate():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(10)
            return b"", b""

        mock_proc = MagicMock()
        mock_proc.communicate = communicate
        mock_proc.kill = MagicMock()
        mock_proc.returncode = None

        with patch("bazel_mcp.bazel.resolve_bazel_binary", return_value="bazel"):
            with patch("asyncio.create_subprocess_exec", return_value=mock_proc):
                with pytest.raises(BazelExecutionError) as exc_info:
                    await run_bazel(["query", "//..."], timeout=0.01)

        assert exc_info.value.return_code == -1
        mock_proc.kill.assert_called_once()
        assert call_count == 2
