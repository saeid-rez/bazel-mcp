"""BUILD file reading MCP tool."""

from pathlib import Path

from bazel_mcp.bazel import find_workspace_root
from bazel_mcp.exceptions import BazelMcpError
from bazel_mcp.server import mcp

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


def _resolve_build_file(workspace: Path, path: str) -> Path:
    """Resolve a BUILD file path safely within the workspace."""
    raw = Path(path)
    candidates: list[Path] = []

    if raw.name in ("BUILD", "BUILD.bazel"):
        candidates.append(workspace / raw)
    elif raw.suffix in (".bazel", ""):
        candidates.append(workspace / raw)
        if raw.suffix == "":
            candidates.append(workspace / f"{raw}/BUILD")
            candidates.append(workspace / f"{raw}/BUILD.bazel")
    else:
        candidates.append(workspace / raw)
        candidates.append(workspace / raw / "BUILD")
        candidates.append(workspace / raw / "BUILD.bazel")

    for candidate in candidates:
        resolved = candidate.resolve()
        try:
            resolved.relative_to(workspace.resolve())
        except ValueError as exc:
            raise BazelMcpError(
                f"Path {path!r} resolves outside the Bazel workspace."
            ) from exc
        if resolved.is_file():
            return resolved

    raise BazelMcpError(
        f"No BUILD file found for {path!r}. Tried: "
        + ", ".join(str(c) for c in candidates)
    )


@mcp.tool(annotations=_READ_ONLY)
async def explain_build_file(path: str) -> str:
    """Return BUILD file contents for analysis by the host LLM.

    path is relative to the workspace root (e.g. foo/bar/BUILD or foo/bar).
    """
    workspace = find_workspace_root()
    build_path = _resolve_build_file(workspace, path)
    rel = build_path.relative_to(workspace.resolve())
    content = build_path.read_text(encoding="utf-8", errors="replace")
    return f"# BUILD file: {rel}\n\n```python\n{content}\n```"
