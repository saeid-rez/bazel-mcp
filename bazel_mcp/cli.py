"""Command-line entry point for the Bazel MCP server."""

from __future__ import annotations

import argparse
import logging
import sys


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="MCP server for Bazel workspaces")
    parser.add_argument(
        "--workspace-root",
        "-w",
        help="Bazel workspace root. Defaults to auto-detection from cwd.",
    )
    parser.add_argument(
        "--bazel-path",
        help="Path to bazel or bazelisk. Defaults to 'bazel'.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        help="Default Bazel command timeout in seconds.",
    )
    parser.add_argument(
        "--max-output-chars",
        type=int,
        help="Maximum stdout/stderr characters returned per stream.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="count",
        default=0,
        help="Increase stderr logging verbosity. Use -vv for debug logs.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)

    logging_level = logging.WARNING
    if args.verbose == 1:
        logging_level = logging.INFO
    elif args.verbose >= 2:
        logging_level = logging.DEBUG
    logging.basicConfig(level=logging_level, stream=sys.stderr)
    logging.getLogger("mcp").setLevel(logging_level)
    logging.getLogger("mcp.server.lowlevel.server").setLevel(logging_level)
    logging.getLogger("mcp.server.fastmcp.server").setLevel(logging_level)

    from bazel_mcp.settings import configure_settings

    configure_settings(
        workspace_root=args.workspace_root,
        bazel_path=args.bazel_path,
        timeout=args.timeout,
        max_output_chars=args.max_output_chars,
    )

    from bazel_mcp.server import mcp

    mcp.run(transport="stdio")
