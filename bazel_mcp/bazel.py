"""Subprocess wrapper around the Bazel CLI."""

from __future__ import annotations

import asyncio
import re
import shutil
import time
from dataclasses import dataclass
from pathlib import Path

from bazel_mcp.exceptions import (
    BazelExecutionError,
    BazelNotFoundError,
    WorkspaceNotFoundError,
)
from bazel_mcp.settings import get_settings

WORKSPACE_MARKERS = ("WORKSPACE", "WORKSPACE.bazel", "MODULE.bazel")

_BUILD_TEST_LOCK = asyncio.Lock()

_TARGET_PATTERN = re.compile(r"^(//|@[\w.-]+//)\S+$")


@dataclass
class BazelResult:
    stdout: str
    stderr: str
    return_code: int
    duration: float


def truncate_output(text: str, max_chars: int | None = None) -> str:
    if max_chars is None:
        max_chars = get_settings().max_output_chars
    if len(text) <= max_chars:
        return text
    keep = max_chars // 2
    return (
        text[:keep]
        + f"\n\n... [{len(text) - max_chars} chars truncated] ...\n\n"
        + text[-keep:]
    )


def _has_workspace_marker(directory: Path) -> bool:
    return any((directory / marker).is_file() for marker in WORKSPACE_MARKERS)


def find_workspace_root(start: Path | None = None) -> Path:
    """Walk up from start (or cwd) to find a Bazel workspace root."""
    settings = get_settings()
    if settings.workspace_root:
        root = Path(settings.workspace_root).resolve()
        if not _has_workspace_marker(root):
            raise WorkspaceNotFoundError(
                f"Workspace root is set to {root} but no workspace marker "
                f"({', '.join(WORKSPACE_MARKERS)}) was found.",
                searched_paths=[str(root)],
            )
        return root

    current = (start or Path.cwd()).resolve()
    searched: list[str] = []
    for directory in [current, *current.parents]:
        searched.append(str(directory))
        if _has_workspace_marker(directory):
            return directory

    raise WorkspaceNotFoundError(
        "No Bazel workspace found. Looked for "
        f"{', '.join(WORKSPACE_MARKERS)} in: " + ", ".join(searched[:10])
        + (" ..." if len(searched) > 10 else ""),
        searched_paths=searched,
    )


def resolve_bazel_binary() -> str:
    settings = get_settings()
    candidate = settings.bazel_path
    if Path(candidate).is_file():
        return candidate
    found = shutil.which(candidate)
    if found:
        return found
    for fallback in ("bazelisk", "bazel"):
        if fallback != candidate:
            found = shutil.which(fallback)
            if found:
                return found
    raise BazelNotFoundError(
        f"Bazel binary not found: {candidate!r}. Use --bazel-path or install bazel/bazelisk."
    )


def normalize_query_pattern(package: str) -> str:
    """Normalize a package or target pattern for bazel query."""
    package = package.strip()
    if not package:
        package = "//..."

    if package.startswith("@"):
        return package

    if not package.startswith("//"):
        package = f"//{package}"

    if ":" in package or package.endswith("/...") or package == "//...":
        return package

    return f"{package}:all"


def validate_target_label(target: str) -> None:
    if not _TARGET_PATTERN.match(target.strip()):
        raise ValueError(
            f"Invalid Bazel target label: {target!r}. "
            "Expected form like //pkg:target, //:target, //pkg/..., or @repo//pkg:target."
        )


def _needs_build_test_lock(args: list[str]) -> bool:
    return bool(args) and args[0] in ("build", "test")


async def run_bazel(
    args: list[str],
    *,
    timeout: int | None = None,
    check: bool = True,
) -> BazelResult:
    """Execute `bazel <args>` asynchronously in the workspace root."""
    settings = get_settings()
    workspace = find_workspace_root()
    bazel = resolve_bazel_binary()
    cmd = [bazel, *args]
    effective_timeout = timeout if timeout is not None else settings.timeout
    max_chars = settings.max_output_chars

    async def _execute() -> BazelResult:
        start = time.monotonic()
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=workspace,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                proc.communicate(),
                timeout=effective_timeout,
            )
        except asyncio.TimeoutError:
            proc.kill()
            try:
                await asyncio.wait_for(proc.communicate(), timeout=5.0)
            except asyncio.TimeoutError:
                pass
            raise BazelExecutionError(
                f"Bazel command timed out after {effective_timeout}s: {' '.join(cmd)}",
                return_code=-1,
                stderr="",
            ) from None

        duration = time.monotonic() - start
        stdout = truncate_output(stdout_bytes.decode(errors="replace"), max_chars)
        stderr = truncate_output(stderr_bytes.decode(errors="replace"), max_chars)
        return_code = proc.returncode or 0

        result = BazelResult(
            stdout=stdout,
            stderr=stderr,
            return_code=return_code,
            duration=duration,
        )
        if check and return_code != 0:
            raise BazelExecutionError(
                f"Bazel command failed (exit {return_code}): {' '.join(cmd)}",
                return_code=return_code,
                stderr=result.stderr,
            )
        return result

    if _needs_build_test_lock(args):
        async with _BUILD_TEST_LOCK:
            return await _execute()
    return await _execute()
