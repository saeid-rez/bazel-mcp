"""Tests for BUILD file resolution."""

from pathlib import Path

import pytest

from bazel_mcp.exceptions import BazelMcpError
from bazel_mcp.tools.explain import _resolve_build_file


def test_resolve_build_file(tmp_path: Path):
    workspace = tmp_path
    (workspace / "foo").mkdir()
    build = workspace / "foo" / "BUILD"
    build.write_text('cc_library(name = "lib")\n')

    resolved = _resolve_build_file(workspace, "foo/BUILD")
    assert resolved == build.resolve()

    resolved2 = _resolve_build_file(workspace, "foo")
    assert resolved2 == build.resolve()


def test_rejects_path_outside_workspace(tmp_path: Path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "MODULE.bazel").write_text("module(name='x')\n")

    outside = tmp_path / "outside"
    outside.mkdir()
    outside_build = outside / "BUILD"
    outside_build.write_text("")

    with pytest.raises(BazelMcpError, match="outside"):
        _resolve_build_file(workspace, str(Path("..") / "outside" / "BUILD"))
