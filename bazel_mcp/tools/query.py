"""Bazel query MCP tools."""

from pathlib import Path

from bazel_mcp.bazel import (
    normalize_query_pattern,
    run_bazel,
    truncate_output_bytes,
    validate_target_label,
)
from bazel_mcp.server import mcp

_READ_ONLY = {
    "readOnlyHint": True,
    "destructiveHint": False,
    "idempotentHint": True,
    "openWorldHint": False,
}


@mcp.tool(annotations=_READ_ONLY)
async def bazel_query(query: str, output_format: str = "label") -> str:
    """Run an arbitrary Bazel query expression.

    Query is read-only but can be expensive on broad patterns like //...
    output_format: label, build, xml, package, location, graph, etc.
    """
    result = await run_bazel(["query", f"--output={output_format}", query])
    return result.stdout


@mcp.tool(annotations=_READ_ONLY)
async def bazel_cquery(
    query: str,
    output_format: str = "label",
    options: list[str] | None = None,
    max_output_bytes: int = 65536,
) -> str:
    """Run a Bazel configured query (cquery) expression.

    Evaluates targets after configuration evaluation, platform resolution,
    and select() branch conditions.

    Args:
        query: Query expression (e.g. deps(//pkg:target) or //pkg:target).
        output_format: Output format (label, label_kind, textproto, proto, jsonproto, etc.).
        options: Optional Bazel flags (e.g. ['--config=ci', '--platforms=//platforms:linux']).
        max_output_bytes: Maximum response size in bytes before safe truncation (default 65536).
    """
    cmd = ["cquery", f"--output={output_format}"]
    if options:
        cmd.extend(options)
    cmd.append(query)
    result = await run_bazel(cmd, max_chars=max_output_bytes * 2)
    return truncate_output_bytes(result.stdout, max_output_bytes)


@mcp.tool(annotations=_READ_ONLY)
async def bazel_aquery(
    query: str,
    output_format: str = "text",
    options: list[str] | None = None,
    max_output_bytes: int = 65536,
) -> str:
    """Run a Bazel action query (aquery) expression.

    Inspects actions generated in the build graph including compiler/linker commands,
    arguments, environment variables, inputs, and outputs.

    Args:
        query: Action query expression (e.g. mnemonic('CppCompile', //pkg:target)).
        output_format: Output format (text, proto, textproto, jsonproto, etc.).
        options: Optional Bazel flags (e.g. ['--include_artifacts=false']).
        max_output_bytes: Maximum response size in bytes before safe truncation (default 65536).
    """
    cmd = ["aquery", f"--output={output_format}"]
    if options:
        cmd.extend(options)
    cmd.append(query)
    result = await run_bazel(cmd, max_chars=max_output_bytes * 2)
    output = result.stdout
    if not output.strip():
        return f"No matching actions found for query: {query}"
    return truncate_output_bytes(output, max_output_bytes)


@mcp.tool(annotations=_READ_ONLY)
async def list_targets(package: str = "//...") -> str:
    """List all targets matching a package pattern.

    Default //... lists targets across the entire workspace (can be slow).
    For a single package use //pkg or pkg (normalized to //pkg:all).
    For a subtree use //pkg/...
    """
    pattern = normalize_query_pattern(package)
    result = await run_bazel(["query", pattern])
    return result.stdout


@mcp.tool(annotations=_READ_ONLY)
async def get_deps(target: str, depth: int = 1) -> str:
    """Get dependencies of a target up to the given depth, excluding the target itself."""
    validate_target_label(target)
    result = await run_bazel(["query", f"deps({target}, {depth}) except {target}"])
    return result.stdout


@mcp.tool(annotations=_READ_ONLY)
async def get_rdeps(target: str, scope: str = "//...") -> str:
    """Find reverse dependencies of a target within scope, excluding the target itself."""
    validate_target_label(target)
    scope_pattern = normalize_query_pattern(scope)
    result = await run_bazel(["query", f"rdeps({scope_pattern}, {target}) except {target}"])
    return result.stdout


@mcp.tool(annotations=_READ_ONLY)
async def show_target_info(target: str) -> str:
    """Show the BUILD rule definition for a target (bazel query --output=build).

    Macro-generated targets may differ from on-disk BUILD files.
    """
    validate_target_label(target)
    result = await run_bazel(["query", "--output=build", target])
    return result.stdout


def _file_to_bazel_label(file_path: str) -> str:
    """Convert a file path to its Bazel package label.
    
    Example: src/lib/BUILD -> //src/lib
             src/lib/foo.go -> //src/lib:foo.go
    """
    file_path = file_path.strip()
    if not file_path:
        return None
    
    path = Path(file_path)
    name = path.name
    
    if name in ("BUILD", "BUILD.bazel"):
        parent = path.parent
        pkg = str(parent).replace("\\", "/")
        if pkg == ".":
            pkg = ""
        return f"//{pkg}" if pkg else "//:"
    
    if name.endswith((".bazel", ".bzl")):
        return None
    
    parent = path.parent
    pkg = str(parent).replace("\\", "/")
    if pkg == ".":
        pkg = ""
    
    base = path.stem if path.suffix else path.name
    
    if not pkg:
        return f"//:{base}"
    return f"//{pkg}:{base}"


@mcp.tool(annotations=_READ_ONLY)
async def find_affected_targets(
    changed_files: list[str],
    scope: str = "//...",
    target_kind: str | None = None,
) -> str:
    """Find all Bazel targets affected by a set of changed files.
    
    This is useful for CI optimization - only rebuild/test what's changed.
    
    Args:
        changed_files: List of file paths (from git diff --name-only).
        scope: Scope to search within (default: //...). Can be a package like //src/...
        target_kind: Optional filter by target kind (e.g., 'cc_library', 'python_library', 'test').
    """
    if not changed_files:
        return "No files provided."
    
    labels = []
    for f in changed_files:
        label = _file_to_bazel_label(f)
        if label:
            labels.append(label)
    
    if not labels:
        return "No valid Bazel targets found in changed files."
    
    file_set = " ".join(labels)
    scope_pattern = normalize_query_pattern(scope)
    
    query = f"rdeps({scope_pattern}, set({file_set}))"
    
    if target_kind:
        query = f"kind('{target_kind}', {query})"
    
    result = await run_bazel(["query", query])
    return result.stdout if result.stdout else "No affected targets found."
