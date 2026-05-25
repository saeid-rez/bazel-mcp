"""Entry point for the Bazel MCP server."""

from bazel_mcp.server import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
