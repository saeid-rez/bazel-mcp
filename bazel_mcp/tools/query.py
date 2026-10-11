"""Bazel query MCP tools."""

import re
from collections import defaultdict
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


_DOT_EDGE_PATTERN = re.compile(r'"([^"]+)"\s*->\s*"([^"]+)"')


def _parse_dot_edges(dot_text: str) -> list[tuple[str, str]]:
    """Extract directed edges (u, v) from Graphviz DOT output."""
    return _DOT_EDGE_PATTERN.findall(dot_text)


@mcp.tool(annotations=_READ_ONLY)
async def get_dependency_path(
    source: str,
    target: str,
    all_paths: bool = False,
    max_depth: int | None = None,
) -> str:
    """Trace dependency chains connecting two targets using somepath or allpaths.

    Finds and displays the dependency path(s) between a source target and a target target.
    Useful for diagnosing dependency cycles and unexpected transitive links.

    Args:
        source: Starting target label (e.g. '//pkg:a').
        target: Destination target label (e.g. '//pkg:b').
        all_paths: If False, returns a single ordered path via 'somepath'.
                   If True, returns all connecting paths via 'allpaths'.
        max_depth: Optional maximum path depth (number of dependency hops).
                   Paths longer than max_depth are omitted.
    """
    validate_target_label(source)
    validate_target_label(target)

    if max_depth is not None and max_depth < 0:
        raise ValueError(f"max_depth must be non-negative, got {max_depth}")

    source = source.strip()
    target = target.strip()

    if not all_paths:
        result = await run_bazel(["query", f"somepath({source}, {target})"])
        nodes = [line.strip() for line in result.stdout.splitlines() if line.strip()]

        if not nodes:
            return f"No path found between {source} and {target}."

        depth = len(nodes) - 1
        if max_depth is not None and depth > max_depth:
            return f"No path found between {source} and {target} within max_depth {max_depth}."

        return " -> ".join(nodes)

    # all_paths is True
    result = await run_bazel(["query", "--output=graph", f"allpaths({source}, {target})"])
    output = result.stdout

    if source == target:
        if source in output:
            return source
        return f"No path found between {source} and {target}."

    edges = _parse_dot_edges(output)
    if not edges:
        return f"No path found between {source} and {target}."

    adj: dict[str, list[str]] = defaultdict(list)
    for u, v in edges:
        if v not in adj[u]:
            adj[u].append(v)

    paths: list[list[str]] = []

    def _dfs(current: str, current_path: list[str]) -> None:
        if max_depth is not None and (len(current_path) - 1) > max_depth:
            return
        if current == target:
            paths.append(list(current_path))
            return
        for neighbor in adj.get(current, []):
            if neighbor not in current_path:
                current_path.append(neighbor)
                _dfs(neighbor, current_path)
                current_path.pop()

    _dfs(source, [source])

    if not paths:
        if max_depth is not None:
            return f"No path found between {source} and {target} within max_depth {max_depth}."
        return f"No path found between {source} and {target}."

    paths.sort(key=lambda p: (len(p), p))
    return "\n".join(" -> ".join(p) for p in paths)


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
