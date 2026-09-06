"""Tests for Bazel MCP CLI."""

import pytest

from bazel_mcp import __version__
from bazel_mcp.cli import _parse_args


def test_cli_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        _parse_args(["--version"])
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert __version__ in captured.out or __version__ in captured.err


def test_cli_args_parsing():
    args = _parse_args([
        "--workspace-root", "/tmp/bazel",
        "--bazel-path", "bazelisk",
        "--timeout", "300",
        "--max-output-chars", "50000",
        "-vv",
    ])
    assert args.workspace_root == "/tmp/bazel"
    assert args.bazel_path == "bazelisk"
    assert args.timeout == 300
    assert args.max_output_chars == 50000
    assert args.verbose == 2
